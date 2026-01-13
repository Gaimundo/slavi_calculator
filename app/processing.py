import numpy as np
import rasterio
from rasterio.mask import mask
from rasterio.warp import calculate_default_transform, reproject, Resampling
import geopandas as gpd
import tempfile
import os

from rasterstats import zonal_stats
from shapely.geometry import mapping
from typing import Tuple, Dict, List, Optional, Union
from dataclasses import dataclass


@dataclass
class RasterBands:
    nir: np.ndarray
    red: np.ndarray
    swir: np.ndarray
    transform: rasterio.Affine
    crs: str
    profile: dict


def load_raster_band(file_path: str, band: int = 1) -> Tuple[np.ndarray, dict]:
    with rasterio.open(file_path) as src:
        data = src.read(band).astype(np.float32)
        profile = src.profile.copy()
        if src.nodata is not None:
            data[data == src.nodata] = np.nan
    return data, profile


def load_multiband_raster(file_path: str, nir_band: int, red_band: int, swir_band: int) -> RasterBands:
    with rasterio.open(file_path) as src:
        nir = src.read(nir_band).astype(np.float32)
        red = src.read(red_band).astype(np.float32)
        swir = src.read(swir_band).astype(np.float32)
        
        if src.nodata is not None:
            nir[nir == src.nodata] = np.nan
            red[red == src.nodata] = np.nan
            swir[swir == src.nodata] = np.nan
        
        return RasterBands(
            nir=nir,
            red=red,
            swir=swir,
            transform=src.transform,
            crs=src.crs.to_string() if src.crs else None,
            profile=src.profile.copy()
        )


def calculate_slavi(nir: np.ndarray, red: np.ndarray, swir: np.ndarray, 
                    epsilon: float = 1e-10) -> np.ndarray:
    denominator = red + swir
    denominator = np.where(denominator == 0, epsilon, denominator)
    
    slavi = nir / denominator
    
    slavi = np.where(np.isfinite(slavi), slavi, np.nan)
    
    return slavi


def load_vector_data(file_path: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(file_path)
    return gdf


def reproject_vector_to_raster_crs(gdf: gpd.GeoDataFrame, raster_crs: str) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    
    if gdf.crs.to_string() != raster_crs:
        gdf = gdf.to_crs(raster_crs)
    
    return gdf


def calculate_zonal_statistics(slavi_array: np.ndarray, 
                                transform: rasterio.Affine,
                                gdf: gpd.GeoDataFrame,
                                stats: List[str] = None) -> gpd.GeoDataFrame:
    if stats is None:
        stats = ['mean', 'min', 'max', 'std', 'count', 'median']
    
    zs = zonal_stats(
        gdf.geometry,
        slavi_array,
        affine=transform,
        stats=stats,
        nodata=np.nan
    )
    
    result_gdf = gdf.copy()
    for stat in stats:
        result_gdf[f'slavi_{stat}'] = [z[stat] if z else None for z in zs]
    
    return result_gdf


def save_slavi_raster(slavi_array: np.ndarray, 
                       profile: dict, 
                       output_path: str) -> str:
    profile.update(
        dtype=rasterio.float32,
        count=1,
        nodata=np.nan
    )
    
    with rasterio.open(output_path, 'w', **profile) as dst:
        dst.write(slavi_array.astype(np.float32), 1)
    
    return output_path


def clip_raster_to_vector(raster_array: np.ndarray,
                          transform: rasterio.Affine,
                          crs: str,
                          gdf: gpd.GeoDataFrame) -> Tuple[np.ndarray, rasterio.Affine]:
    with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        profile = {
            'driver': 'GTiff',
            'dtype': raster_array.dtype,
            'width': raster_array.shape[1],
            'height': raster_array.shape[0],
            'count': 1,
            'crs': crs,
            'transform': transform,
            'nodata': np.nan
        }
        
        with rasterio.open(tmp_path, 'w', **profile) as dst:
            dst.write(raster_array, 1)
        
        with rasterio.open(tmp_path) as src:
            geometries = [mapping(geom) for geom in gdf.geometry]
            clipped, clipped_transform = mask(src, geometries, crop=True, nodata=np.nan)
        
        return clipped[0], clipped_transform
    
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def process_slavi_analysis(nir_data: np.ndarray,
                           red_data: np.ndarray,
                           swir_data: np.ndarray,
                           raster_profile: dict,
                           vector_gdf: gpd.GeoDataFrame) -> Dict:
    slavi = calculate_slavi(nir_data, red_data, swir_data)
    
    raster_crs = raster_profile.get('crs')
    if raster_crs:
        vector_gdf = reproject_vector_to_raster_crs(vector_gdf, str(raster_crs))
    
    transform = raster_profile['transform']
    results_gdf = calculate_zonal_statistics(slavi, transform, vector_gdf)
    
    return {
        'slavi_array': slavi,
        'results_gdf': results_gdf,
        'profile': raster_profile
    }


def get_raster_info(file_path: str) -> Dict:
    with rasterio.open(file_path) as src:
        return {
            'width': src.width,
            'height': src.height,
            'count': src.count,
            'crs': str(src.crs) if src.crs else None,
            'bounds': src.bounds,
            'transform': src.transform,
            'dtype': str(src.dtypes[0]),
            'nodata': src.nodata
        }


def validate_inputs(nir: np.ndarray, red: np.ndarray, swir: np.ndarray) -> bool:
    if nir.shape != red.shape or nir.shape != swir.shape:
        raise ValueError("All bands must have the same size!")
    
    if nir.size == 0:
        raise ValueError("Raster data is empty!")
    
    return True
