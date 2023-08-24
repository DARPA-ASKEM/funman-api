#!/usr/bin/env python3

import json
import sys
from pathlib import Path

import requests


def query(url: str, model: dict, request: dict, timeout: float = None):
    endpoint = f"{url.rstrip('/')}/api/queries"
    payload = {"model": model, "request": request}
    response = requests.post(endpoint, json=payload, timeout=timeout)
    response.raise_for_status()
    return json.loads(response.content.decode())


def read_to_dict(path: str):
    fpath = Path(path).resolve()
    if not fpath.exists():
        raise FileNotFoundError(f"{path} not found")
    if not fpath.is_file():
        raise Exception(f"{path} is not a file")
    return json.loads(fpath.read_bytes())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="POST query to funman")
    parser.add_argument(
        "url", type=str, help="The base URL of the funman server"
    )
    parser.add_argument("model", type=str, help="the path to the model json")
    parser.add_argument(
        "-r", "--request", type=str, help="the path to the request json"
    )
    args = parser.parse_args()

    model = read_to_dict(args.model)
    if args.request is None:
        print("Using default request:", file=sys.stderr)
        request = {}
        payload = [f'"model": <Contents of {args.model}>', '"request": {}']
    else:
        print(f"Using request from path: {args.request}", file=sys.stderr)
        request = read_to_dict(args.request)
        payload = [
            f'"model": <Contents of {args.model}>',
            f'"request": <Contents of {args.request}>',
        ]
    print("The POST payload: \n{", file=sys.stderr)
    for p in payload:
        print(f"    {p}", file=sys.stderr)
    print("}", file=sys.stderr)

    results = query(args.url, model, request)
    print(f"Query received work id: {results['id']}", file=sys.stderr)
    print(results["id"], file=sys.stdout)
