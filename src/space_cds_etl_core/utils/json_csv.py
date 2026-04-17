
import json
import pandas as pd
from collections.abc import MutableMapping
from datetime import datetime
import gcsfs
import io
import re
from space_cds_etl_core.utils.logger import CloudLogger
logger = CloudLogger().get_logger()

def sanitize_data(content):
    if not isinstance(content, str):
        return content
    try:
        cleaned = content.replace("\\n", "")
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.info(f"Error decoding JSON in Content field: {e}")
        return content


def get_values_for_key(records):
    for item in records:
        if 'Content' in item:
            item['Content'] = sanitize_data(item['Content'])
    return records


def flatten_dict(d, parent_key='', sep='_'):
    items = {}
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, MutableMapping):
            items.update(flatten_dict(v, new_key, sep))
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, (MutableMapping, list)):
                    items.update(flatten_dict(item, f"{new_key}_{i}", sep))
                else:
                    items[f"{new_key}_{i}"] = item
        else:
            items[new_key] = v
    return items

def get_files(fs, input_pattern):
    if not input_pattern.startswith('gs://'):
        logger.error("Input path must start with gs://")
        return []
    path_wo_gs = input_pattern[5:]
    bucket, _, pattern = path_wo_gs.partition('/')
    prefix = pattern.rsplit('/', 1)[0]
    files = fs.glob(f"{bucket}/{prefix}/**")
    regex = re.compile(pattern)
    return [f"gs://{f}" for f in files if regex.search(f)]

def load_json(fs, path):
    try:
        with fs.open(path, 'r') as f:
            content = f.read().replace('\\\\n', '').replace('\\\\r', '')
            return json.loads(content)
    except Exception as e:
        logger.error(f"Error loading JSON: {e}")
        return None

def write_csv(fs, output_dir, country, records, date):
    df = pd.DataFrame([flatten_dict(r) for r in records])
    df.columns = [c.removeprefix('Content_') for c in df.columns]
    fname = f"{output_dir}/access_{country}_{date}.csv"
    with io.StringIO() as buf:
        df.to_csv(buf, index=False)
        buf.seek(0)
        with fs.open(fname, 'w') as fout:
            fout.write(buf.read())
    logger.info(f"Wrote {fname} ({len(df)} records)")
    return fname



def group_by_country(records, country_code=None):
    grouped = {}
    for r in records:
        try:
            c = r['Content']['headers']['X-Country']
            if country_code and c != country_code:
                continue
            grouped.setdefault(c, []).append(r)
        except Exception as e:
            logger.error(f"Missing country: {e}")
    return grouped


def process_json_to_csv(input_pattern, output_dir='gen_out', country_code=None):
    fs = gcsfs.GCSFileSystem()
    files = get_files(fs, input_pattern)
    if not files:
        logger.info(f"No files matched: {input_pattern}")
        return
    date = datetime.now().strftime("%d%m%Y")
    for path in files:
        logger.info(f"Processing: {path}")
        data = load_json(fs, path)
        if data is None:
            continue
        records = get_values_for_key(data if isinstance(data, list) else [data])
        grouped = group_by_country(records, country_code)
        for c, recs in grouped.items():
            csv_file = write_csv(fs, output_dir, c, recs, date)
        return csv_file, path
    