import streamlit as st
import numpy as np
import geopandas as gpd
import pandas as pd
import tempfile
import os
import io
from pathlib import Path

import rasterio
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from processing import (
    load_raster_band,
    load_multiband_raster,
    calculate_slavi,
    load_vector_data,
    calculate_zonal_statistics,
    reproject_vector_to_raster_crs,
    save_slavi_raster,
    get_raster_info,
    validate_inputs,
    process_slavi_analysis
)


st.set_page_config(
    page_title="SLAVI Calculator",
    layout="wide",
    initial_sidebar_state="expanded"
)

DATA_DIR = Path(__file__).parent.parent / "data"

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #2e7d32;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .info-box {
        background-color: #e8f5e9;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #2e7d32;
    }
    .warning-box {
        background-color: #fff3e0;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #ff9800;
    }
    .stMetric {
        background-color: #f5f5f5;
        padding: 1rem;
        border-radius: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)


def main():
    st.markdown('<h1 class="main-header">SLAVI Calculator</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Specific Leaf Area Vegetation Index</p>', unsafe_allow_html=True)
    
    st.sidebar.header("Input data configuration")
    
    data_source = st.sidebar.radio(
        "Data source:",
        ["Local files (data folder)", "Upload files"],
        help="Choose whether to use files from the data folder or upload your own"
    )
    
    nir_data = None
    red_data = None
    swir_data = None
    raster_profile = None
    vector_gdf = None
    
    if data_source == "Local files (data folder)":
        st.sidebar.subheader("Raster data")
        
        raster_files = list(DATA_DIR.glob("*.tif")) + list(DATA_DIR.glob("*.tiff")) + list(DATA_DIR.glob("*.jp2"))
        raster_names = [f.name for f in raster_files]
        
        if raster_names:
            nir_file_name = st.sidebar.selectbox(
                "NIR",
                raster_names,
                index=raster_names.index("B08.jp2") if "B08.jp2" in raster_names else 0,
                help="Sentinel-2: B08"
            )
            red_file_name = st.sidebar.selectbox(
                "Red",
                raster_names,
                index=raster_names.index("B04.jp2") if "B04.jp2" in raster_names else 0,
                help="Sentinel-2: B04"
            )
            swir_file_name = st.sidebar.selectbox(
                "SWIR",
                raster_names,
                index=raster_names.index("B11_10m.tif") if "B11_10m.tif" in raster_names else 0,
                help="Sentinel-2: B11 (przeskalowany do 10m)"
            )
            
            if st.sidebar.button("Load raster data", type="primary"):
                try:
                    with st.spinner("Loading raster data..."):
                        nir_path = DATA_DIR / nir_file_name
                        red_path = DATA_DIR / red_file_name
                        swir_path = DATA_DIR / swir_file_name
                        
                        nir_data, nir_profile = load_raster_band(str(nir_path))
                        red_data, _ = load_raster_band(str(red_path))
                        swir_data, _ = load_raster_band(str(swir_path))
                        raster_profile = nir_profile
                        
                        st.session_state['nir_data'] = nir_data
                        st.session_state['red_data'] = red_data
                        st.session_state['swir_data'] = swir_data
                        st.session_state['raster_profile'] = raster_profile
                        
                        st.sidebar.success(f"Loaded raster data!\nSize: {nir_data.shape}")
                except Exception as e:
                    st.sidebar.error(f"Loading error: {str(e)}")
            
            if 'nir_data' in st.session_state:
                nir_data = st.session_state['nir_data']
                red_data = st.session_state['red_data']
                swir_data = st.session_state['swir_data']
                raster_profile = st.session_state['raster_profile']
        else:
            st.sidebar.warning("No raster files in the data/ folder")
        
        st.sidebar.subheader("Vector data")
        
        vector_files = list(DATA_DIR.glob("*.geojson")) + list(DATA_DIR.glob("*.json"))
        vector_names = [f.name for f in vector_files]
        
        if vector_names:
            vector_file_name = st.sidebar.selectbox(
                "GeoJSON file with areas",
                vector_names,
                index=vector_names.index("plots.geojson") if "plots.geojson" in vector_names else 0
            )
            
            try:
                vector_path = DATA_DIR / vector_file_name
                vector_gdf = load_vector_data(str(vector_path))
                st.sidebar.success(f"Loaded {len(vector_gdf)} objects")
            except Exception as e:
                st.sidebar.error(f"Error: {str(e)}")
        else:
            st.sidebar.warning("No GeoJSON files in the data/ folder")
    
    else:
        input_mode = st.sidebar.radio(
            "Raster data loading mode:",
            ["Separate files (NIR, Red, SWIR)", "Multiband raster"],
            help="Choose the method of loading raster data"
        )
        
        st.sidebar.subheader("🗺️ Raster data")
        
        if input_mode == "Separate files (NIR, Red, SWIR)":
            nir_file = st.sidebar.file_uploader(
                "NIR band (GeoTIFF)",
                type=['tif', 'tiff', 'jp2'],
                key='nir',
                help="Upload a GeoTIFF file with the NIR band"
            )
            red_file = st.sidebar.file_uploader(
                "Red band (GeoTIFF)",
                type=['tif', 'tiff', 'jp2'],
                key='red',
                help="Upload a GeoTIFF file with the Red band"
            )
            swir_file = st.sidebar.file_uploader(
                "SWIR band (GeoTIFF)",
                type=['tif', 'tiff', 'jp2'],
                key='swir',
                help="Upload a GeoTIFF file with the SWIR band"
            )
            
            if nir_file and red_file and swir_file:
                try:
                    with tempfile.TemporaryDirectory() as tmpdir:
                        nir_path = os.path.join(tmpdir, "nir.tif")
                        red_path = os.path.join(tmpdir, "red.tif")
                        swir_path = os.path.join(tmpdir, "swir.tif")
                        
                        with open(nir_path, 'wb') as f:
                            f.write(nir_file.getvalue())
                        with open(red_path, 'wb') as f:
                            f.write(red_file.getvalue())
                        with open(swir_path, 'wb') as f:
                            f.write(swir_file.getvalue())
                        
                        nir_data, nir_profile = load_raster_band(nir_path)
                        red_data, red_profile = load_raster_band(red_path)
                        swir_data, swir_profile = load_raster_band(swir_path)
                        raster_profile = nir_profile
                        
                        st.sidebar.success("Raster data loaded!")
                        
                except Exception as e:
                    st.sidebar.error(f"Error loading raster data: {str(e)}")
        
        else:
            multi_file = st.sidebar.file_uploader(
                "Multiband raster (GeoTIFF)",
                type=['tif', 'tiff'],
                key='multi',
                help="Upload a multiband GeoTIFF file"
            )
            
            if multi_file:
                try:
                    with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as tmp:
                        tmp.write(multi_file.getvalue())
                        tmp_path = tmp.name
                    
                    info = get_raster_info(tmp_path)
                    st.sidebar.info(f"Number of bands: {info['count']}")
                    
                    col1, col2, col3 = st.sidebar.columns(3)
                    with col1:
                        nir_band = st.number_input("NIR", min_value=1, max_value=info['count'], value=min(4, info['count']), key='nir_band')
                    with col2:
                        red_band = st.number_input("Red", min_value=1, max_value=info['count'], value=min(3, info['count']), key='red_band')
                    with col3:
                        swir_band = st.number_input("SWIR", min_value=1, max_value=info['count'], value=min(5, info['count']), key='swir_band')
                    
                    bands = load_multiband_raster(tmp_path, nir_band, red_band, swir_band)
                    nir_data = bands.nir
                    red_data = bands.red
                    swir_data = bands.swir
                    raster_profile = bands.profile
                    
                    os.unlink(tmp_path)
                    st.sidebar.success("Raster data loaded!")
                    
                except Exception as e:
                    st.sidebar.error(f"Error loading raster data: {str(e)}")
        
        st.sidebar.subheader("Vector data")
        vector_file = st.sidebar.file_uploader(
            "GeoJSON file with areas",
            type=['geojson', 'json'],
            help="Upload a GeoJSON file with polygons for zonal analysis"
        )
        
        if vector_file:
            try:
                vector_content = vector_file.getvalue().decode('utf-8')
                with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as tmp:
                    tmp.write(vector_content)
                    tmp_path = tmp.name
                
                vector_gdf = load_vector_data(tmp_path)
                os.unlink(tmp_path)
                
                st.sidebar.success(f"Loaded {len(vector_gdf)} features")
                
            except Exception as e:
                st.sidebar.error(f"Error loading GeoJSON: {str(e)}")
    
    if nir_data is not None and red_data is not None and swir_data is not None:
        
        try:
            validate_inputs(nir_data, red_data, swir_data)
        except ValueError as e:
            st.error(f"{str(e)}")
            return
        

        st.header("Analysis Results")
        
        with st.spinner("Calculating SLAVI index..."):
            slavi = calculate_slavi(nir_data, red_data, swir_data)
        
        col1, col2, col3, col4 = st.columns(4)
        
        valid_slavi = slavi[np.isfinite(slavi)]
        
        with col1:
            st.metric("Average SLAVI", f"{np.nanmean(valid_slavi):.4f}")
        with col2:
            st.metric("Min SLAVI", f"{np.nanmin(valid_slavi):.4f}")
        with col3:
            st.metric("Max SLAVI", f"{np.nanmax(valid_slavi):.4f}")
        with col4:
            st.metric("Std. dev.", f"{np.nanstd(valid_slavi):.4f}")
        
        st.subheader("SLAVI index map")
        
        fig, ax = plt.subplots(figsize=(12, 8))
        
        vmin = np.nanpercentile(valid_slavi, 2)
        vmax = np.nanpercentile(valid_slavi, 98)
        
        cmap = plt.cm.RdYlGn
        im = ax.imshow(slavi, cmap=cmap, vmin=vmin, vmax=vmax)
        ax.set_title("SLAVI index", fontsize=14)
        ax.axis('off')
        
        cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label('SLAVI', fontsize=12)
        
        st.pyplot(fig)
        plt.close()
        
        st.subheader("SLAVI value distribution")
        
        fig_hist, ax_hist = plt.subplots(figsize=(10, 4))
        ax_hist.hist(valid_slavi.flatten(), bins=100, color='#4CAF50', alpha=0.7, edgecolor='darkgreen')
        ax_hist.set_xlabel('SLAVI value')
        ax_hist.set_ylabel('Number of pixels')
        ax_hist.set_title('SLAVI value histogram')
        ax_hist.axvline(np.nanmean(valid_slavi), color='red', linestyle='--', label=f'Mean: {np.nanmean(valid_slavi):.3f}')
        ax_hist.legend()
        
        st.pyplot(fig_hist)
        plt.close()
        
        if vector_gdf is not None:
            st.subheader("Zonal statistics")
            
            with st.spinner("Calculating zonal statistics..."):
                if raster_profile.get('crs'):
                    vector_gdf_reproj = reproject_vector_to_raster_crs(
                        vector_gdf, 
                        str(raster_profile['crs'])
                    )
                else:
                    vector_gdf_reproj = vector_gdf
                
                results_gdf = calculate_zonal_statistics(
                    slavi,
                    raster_profile['transform'],
                    vector_gdf_reproj
                )
            
            display_cols = [col for col in results_gdf.columns if col != 'geometry']
            st.dataframe(
                results_gdf[display_cols].round(4),
                use_container_width=True
            )
            
            if 'slavi_mean' in results_gdf.columns:
                st.subheader("Average SLAVI values chart")
                
                fig_bar, ax_bar = plt.subplots(figsize=(10, 5))
                
                if 'name' in results_gdf.columns:
                    labels = results_gdf['name'].astype(str)
                elif 'id' in results_gdf.columns:
                    labels = results_gdf['id'].astype(str)
                else:
                    labels = [f"Obszar {i+1}" for i in range(len(results_gdf))]
                
                means = results_gdf['slavi_mean'].values
                stds = results_gdf['slavi_std'].values if 'slavi_std' in results_gdf.columns else None
                
                bars = ax_bar.bar(range(len(labels)), means, color='#4CAF50', alpha=0.8)
                
                if stds is not None:
                    ax_bar.errorbar(range(len(labels)), means, yerr=stds, fmt='none', color='black', capsize=5)
                
                ax_bar.set_xticks(range(len(labels)))
                ax_bar.set_xticklabels(labels, rotation=45, ha='right')
                ax_bar.set_ylabel('Average SLAVI value')
                ax_bar.set_title('Average SLAVI value for individual areas')
                
                plt.tight_layout()
                st.pyplot(fig_bar)
                plt.close()
            
            st.subheader("Interactive map")
            
            try:
                map_gdf = results_gdf.to_crs("EPSG:4326")
                
                centroid = map_gdf.geometry.union_all().centroid
                center = [centroid.y, centroid.x]
                
                m = folium.Map(location=center, zoom_start=14)
                
                folium.TileLayer('OpenStreetMap').add_to(m)
                folium.TileLayer(
                    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                    attr='Esri',
                    name='Esri Satellite'
                ).add_to(m)
                
                if 'slavi_mean' in map_gdf.columns:
                    slavi_min = map_gdf['slavi_mean'].min()
                    slavi_max = map_gdf['slavi_mean'].max()
                    
                    def get_color(value):
                        if pd.isna(value):
                            return '#808080'
                        norm = (value - slavi_min) / (slavi_max - slavi_min + 1e-10)
                        cmap = plt.cm.RdYlGn
                        rgba = cmap(norm)
                        return mcolors.rgb2hex(rgba[:3])
                    
                    slavi_layer = folium.FeatureGroup(name='SLAVI Index')
                    
                    for idx, row in map_gdf.iterrows():
                        color = get_color(row['slavi_mean'])
                        
                        tooltip_text = f"""
                        <b>Area:</b> {row.get('name', idx)}<br>
                        <b>Average SLAVI:</b> {row['slavi_mean']:.4f}<br>
                        <b>Min:</b> {row.get('slavi_min', 'N/A')}<br>
                        <b>Max:</b> {row.get('slavi_max', 'N/A')}<br>
                        <b>Std. dev.:</b> {row.get('slavi_std', 'N/A')}
                        """
                        
                        folium.GeoJson(
                            row.geometry.__geo_interface__,
                            style_function=lambda x, color=color: {
                                'fillColor': color,
                                'color': 'black',
                                'weight': 2,
                                'fillOpacity': 0.6
                            },
                            tooltip=folium.Tooltip(tooltip_text)
                        ).add_to(slavi_layer)
                    
                    slavi_layer.add_to(m)
                
                folium.LayerControl().add_to(m)
                
                st_folium(m, width=800, height=500)
                
                st.session_state['folium_map'] = m
                
            except Exception as e:
                st.warning(f"Cannot display interactive map: {str(e)}")
            
            st.subheader("Export results")
            
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                csv = results_gdf.drop(columns=['geometry']).to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name="slavi_statistics.csv",
                    mime="text/csv"
                )
            
            with col2:
                geojson_str = results_gdf.to_json()
                st.download_button(
                    label="Download GeoJSON",
                    data=geojson_str,
                    file_name="slavi_results.geojson",
                    mime="application/json"
                )
            
            with col3:
                tiff_buffer = io.BytesIO()
                output_profile = raster_profile.copy()
                output_profile.update(
                    driver='GTiff',
                    dtype=rasterio.float32,
                    count=1,
                    nodata=np.nan
                )
                
                with rasterio.io.MemoryFile() as memfile:
                    with memfile.open(**output_profile) as dst:
                        dst.write(slavi.astype(np.float32), 1)
                    tiff_data = memfile.read()
                
                st.download_button(
                    label="Download SLAVI (GeoTIFF)",
                    data=tiff_data,
                    file_name="slavi_index.tif",
                    mime="image/tiff"
                )
            
            with col4:
                fig_export, ax_export = plt.subplots(figsize=(12, 10), dpi=150)
                vmin = np.nanpercentile(valid_slavi, 2)
                vmax = np.nanpercentile(valid_slavi, 98)
                im = ax_export.imshow(slavi, cmap=plt.cm.RdYlGn, vmin=vmin, vmax=vmax)
                ax_export.set_title("SLAVI Index", fontsize=14)
                ax_export.axis('off')
                cbar = plt.colorbar(im, ax=ax_export, fraction=0.046, pad=0.04)
                cbar.set_label('SLAVI', fontsize=12)
                
                buf = io.BytesIO()
                fig_export.savefig(buf, format='png', bbox_inches='tight', dpi=150)
                buf.seek(0)
                plt.close(fig_export)
                
                st.download_button(
                    label="Download map (PNG)",
                    data=buf.getvalue(),
                    file_name="slavi_map.png",
                    mime="image/png"
                )
            
            with col5:
                if 'folium_map' in st.session_state:
                    map_html = st.session_state['folium_map']._repr_html_()
                    st.download_button(
                        label="Download map (HTML)",
                        data=map_html,
                        file_name="slavi_interactive_map.html",
                        mime="text/html"
                    )
        
        else:
            st.info("Upload a GeoJSON file with areas to calculate zonal statistics.")
            
            st.subheader("Export SLAVI raster")
            
            output_profile = raster_profile.copy()
            output_profile.update(
                driver='GTiff',
                dtype=rasterio.float32,
                count=1,
                nodata=np.nan
            )
            
            with rasterio.io.MemoryFile() as memfile:
                with memfile.open(**output_profile) as dst:
                    dst.write(slavi.astype(np.float32), 1)
                tiff_data = memfile.read()
            
            st.download_button(
                label="Download SLAVI (GeoTIFF)",
                data=tiff_data,
                file_name="slavi_index.tif",
                mime="image/tiff"
            )
    
    else:
        # Instrukcje
        st.markdown("""
        <div class="info-box">
        <h3>How to get started?</h3>
        <ol>
            <li>Upload raster data (NIR, Red, SWIR bands) in GeoTIFF format</li>
            <li>Optionally upload a GeoJSON file with areas for zonal analysis</li>
            <li>The application will automatically calculate the SLAVI index and display the results</li>
        </ol>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="warning-box">
        <h4>Data requirements:</h4>
        <ul>
            <li><b>Raster data:</b> GeoTIFF format with georeferencing</li>
            <li><b>Vector data:</b> GeoJSON format (EPSG:4326 or other with CRS definition)</li>
            <li><b>Bands:</b> NIR (~842nm), Red (~665nm), SWIR (~1610nm)</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
    
    # Stopka
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align: center; color: #666;">
        SLAVI Calculator v1.0 | Built with Streamlit, GeoPandas, and Rasterio
        </div>
        """,
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
