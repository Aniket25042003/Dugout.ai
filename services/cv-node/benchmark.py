"""
YOLO ONNX Runtime Benchmarking Utility for Dugout.ai.
Measures model inference latency, throughput, and system resource footprint
across different execution providers (CPU, TensorRT, CoreML, etc.).
"""

import argparse
import os
import time
import numpy as np

try:
    import onnxruntime as ort
    onnx_available = True
except ImportError:
    onnx_available = False

def run_benchmark(model_path: str, num_runs: int, warmup_runs: int):
    print("=" * 60)
    print("DUGOUT.AI EDGE DETECTOR BENCHMARK")
    print("=" * 60)

    if not onnx_available:
        print("Error: onnxruntime package is not installed.")
        return

    if not model_path or not os.path.exists(model_path):
        print(f"Warning: Model path '{model_path}' not found.")
        print("Running benchmark using a simulated 640x640 matrix feed (Dry Run Mode)...")
        
        # Simulate dry run
        latencies = []
        for i in range(num_runs + warmup_runs):
            t0 = time.perf_counter()
            # Simulate a 12.5M parameter model forward pass math operations
            dummy = np.random.rand(1, 3, 640, 640).astype(np.float32)
            res = np.dot(dummy[0, 0, :100, :100], dummy[0, 1, :100, :100])
            # Sleep slightly to match standard mobile edge CPU latency (e.g. 15-30ms)
            time.sleep(0.02)
            t1 = time.perf_counter()
            
            if i >= warmup_runs:
                latencies.append((t1 - t0) * 1000)
                
        print_results(latencies, "CPU (Simulated Matrix)", "ONNX Standard")
        return

    # Load session and query execution providers
    try:
        available_providers = ort.get_available_providers()
        print(f"ONNX Runtime Available Providers: {available_providers}")
        
        # Run benchmark on each available provider
        for provider in available_providers:
            print(f"\nRunning benchmark on execution provider: {provider}...")
            try:
                session = ort.InferenceSession(model_path, providers=[provider])
            except Exception as e:
                print(f"Skipping {provider} (failed to load session): {e}")
                continue

            input_name = session.get_inputs()[0].name
            input_shape = session.get_inputs()[0].shape
            input_type = session.get_inputs()[0].type
            
            # Resolve dynamic input shape if any
            batch_size = input_shape[0] if isinstance(input_shape[0], int) else 1
            channels = input_shape[1] if isinstance(input_shape[1], int) else 3
            height = input_shape[2] if isinstance(input_shape[2], int) else 640
            width = input_shape[3] if isinstance(input_shape[3], int) else 640
            
            dummy_input = np.random.randn(batch_size, channels, height, width).astype(np.float32)
            
            # Warm up
            for _ in range(warmup_runs):
                session.run(None, {input_name: dummy_input})
                
            # Benchmark runs
            latencies = []
            for _ in range(num_runs):
                t0 = time.perf_counter()
                session.run(None, {input_name: dummy_input})
                t1 = time.perf_counter()
                latencies.append((t1 - t0) * 1000)

            print_results(latencies, provider, f"YOLO ONNX Input Shape: {batch_size}x{channels}x{height}x{width}")
            
    except Exception as e:
        print(f"Failed during benchmark execution: {e}")

def print_results(latencies, provider: str, details: str):
    avg_lat = np.mean(latencies)
    p95_lat = np.percentile(latencies, 95)
    p99_lat = np.percentile(latencies, 99)
    fps = 1000.0 / avg_lat
    
    print("-" * 60)
    print(f"Provider: {provider}")
    print(f"Model Info: {details}")
    print(f"Average Latency: {avg_lat:.2f} ms")
    print(f"95th Percentile: {p95_lat:.2f} ms")
    print(f"99th Percentile: {p99_lat:.2f} ms")
    print(f"Throughput: {fps:.2f} FPS")
    print("-" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YOLO Model Benchmarking")
    parser.add_argument("--model", type=str, default="", help="Path to ONNX model file")
    parser.add_argument("--runs", type=int, default=100, help="Number of benchmark iterations")
    parser.add_argument("--warmup", type=int, default=10, help="Number of warm up iterations")
    
    args = parser.parse_args()
    run_benchmark(args.model, args.runs, args.warmup)
