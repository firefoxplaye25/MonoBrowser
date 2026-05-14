import json
import gzip
import os

def save_mlhjson(filepath, data):
    """Saves data to a compressed .mlhjson file."""
    if not filepath.endswith('.mlhjson'):
        filepath += '.mlhjson'
    
    json_data = json.dumps(data, indent=2).encode('utf-8')
    with gzip.open(filepath, 'wb') as f:
        f.write(json_data)

def load_mlhjson(filepath, default_data=None):
    """Loads data from a compressed .mlhjson file."""
    if not filepath.endswith('.mlhjson'):
        filepath += '.mlhjson'
        
    if not os.path.exists(filepath):
        if default_data is not None:
            save_mlhjson(filepath, default_data)
            return default_data
        return {}
        
    try:
        with gzip.open(filepath, 'rb') as f:
            json_data = f.read().decode('utf-8')
            return json.loads(json_data)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return default_data if default_data is not None else {}
