#!/bin/bash

uvicorn funman.api.api:app --host 0.0.0.0 --port 8190

