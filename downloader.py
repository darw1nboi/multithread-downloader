import requests
import threading
import os
import shutil
import re
from tqdm import tqdm

TEMP_FOLDER = "segments"
MAX_THREADS = 8


def get_filename_from_headers(headers, default="downloaded_file.bin"):
    if "Content-Disposition" in headers:
        cd = headers["Content-Disposition"]
        match = re.findall(r'filename="?([^\";]+)"?', cd)
        if match:
            return match[0]
    return default


def download_segment(url, start, end, segment_num, progress_bars, stop_event):
    headers = {"Range": f"bytes={start}-{end}"}
    r = requests.get(url, headers=headers, stream=True)
    part_file = os.path.join(TEMP_FOLDER, f"part_{segment_num}")
    with open(part_file, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024):
            if stop_event.is_set():
                return
            if chunk:
                f.write(chunk)
                progress_bars[segment_num].update(len(chunk))


def main():
    num_threads = int(input("Number of threads to use: "))
    url = input("Copy the file URL: ").strip()
    file_path = input("Choose the path and file name: ").strip()

    if num_threads > MAX_THREADS:
        print(f"\nThe maximum amount of threads exceeded (max {MAX_THREADS})")
        return

    r = requests.head(url, allow_redirects=True)

    if "Content-Length" not in r.headers:
        r = requests.get(url, stream=True)
        if "Content-Length" not in r.headers:
            print("\nInvalid URL or missing Content-Length header.")
            filename = get_filename_from_headers(r.headers, "downloaded_file.bin")
            if not file_path:
                file_path = os.path.join(os.getcwd(), filename)
            total_size = None
            with open(file_path, "wb") as f, tqdm(unit="B", unit_scale=True, desc="Downloading") as bar:
                for chunk in r.iter_content(1024):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))
            print("\nDownload finished ->", file_path)
            return

    total_size = int(r.headers["Content-Length"])

    if not file_path:
        filename = get_filename_from_headers(r.headers, "downloaded_file.bin")
        file_path = os.path.join(os.getcwd(), filename)

    print("\n" + "─" * 100)
    print(f"File size: {total_size / 1024 / 1024:.2f} MB")
    print("─" * 100)

    os.makedirs(TEMP_FOLDER, exist_ok=True)
    part_size = total_size // num_threads

    global_progress = tqdm(
        total=total_size, unit="B", unit_scale=True,
        desc="Total", position=0
    )

    progress_bars = [
        tqdm(
            total=part_size if i < num_threads - 1 else total_size - part_size * (num_threads - 1),
            unit="B", unit_scale=True, desc=f"Thread {i}", position=i+1
        )
        for i in range(num_threads)
    ]

    threads = []
    stop_event = threading.Event()
    for i in range(num_threads):
        start = i * part_size
        end = start + part_size - 1 if i < num_threads - 1 else total_size - 1
        t = threading.Thread(target=download_segment, args=(url, start, end, i, progress_bars, stop_event))
        threads.append(t)
        t.start()

    while any(t.is_alive() for t in threads):
        downloaded = sum(pbar.n for pbar in progress_bars)
        global_progress.n = downloaded
        global_progress.refresh()

    for t in threads:
        t.join()

    with open(file_path, "wb") as outfile:
        for i in range(num_threads):
            part_file = os.path.join(TEMP_FOLDER, f"part_{i}")
            with open(part_file, "rb") as infile:
                outfile.write(infile.read())
            os.remove(part_file)

    if os.path.exists(TEMP_FOLDER):
        shutil.rmtree(TEMP_FOLDER)

    for pbar in progress_bars:
        pbar.close()
    global_progress.close()

    print("\n" + "─" * 100)
    print(f"Your download is finished -> {file_path}")
    print("─" * 100)


if __name__ == "__main__":
    main()
