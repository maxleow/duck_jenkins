import os
import json

def get_build_info(file_name: str):
    file_name = os.path.abspath('.') + f'/data/{file_name}'
    with open(file_name) as jf:
        return json.load(jf)
