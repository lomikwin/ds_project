from grid_calculator import generate_grid_coordinates
from pyproj import Transformer
import pandas as pd


NORTH = 38.30   # Yeoncheon
SOUTH = 36.87   # Anseong
EAST = 127.83   # Yangpyeong
WEST = 126.20   # Incheon/Ganghwa (Mainland approx)

coord = generate_grid_coordinates(NORTH , SOUTH , EAST , WEST ,overlap_ratio=0.85 )
proj_katec = "+proj=tmerc +lat_0=38 +lon_0=128 +k=0.9999 +x_0=400000 +y_0=600000 +ellps=bessel +units=m +no_defs"
transformer = Transformer.from_crs("epsg:4326", proj_katec, always_xy=True)
new_list = []
for lon, lat in coord :
    
    katec_x, katec_y = transformer.transform(lat, lon)
    new_list.append((lat, lon , katec_x , katec_y ))

geographic_master_table = pd.DataFrame(new_list , columns = ['lat' , 'lon' , 'katec_x' , 'katec_y'])
geographic_master_table['idx'] = geographic_master_table.index + 1
columns  = ['idx' ,'lat' , 'lon' , 'katec_x' , 'katec_y']
geographic_master_table = geographic_master_table[columns]

geographic_master_table.to_parquet("geographic_master_table.parquet")