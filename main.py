# Author: ssoft.tou
# Company: www.startiasoft.co.jp
# Created: 2024-10-22
import os
import json
import re
import csv
import requests
from bs4 import BeautifulSoup
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import warnings
from requests.exceptions import RequestsDependencyWarning
from datetime import datetime
import subprocess

# Suppress the RequestsDependencyWarning
warnings.filterwarnings("ignore", category=RequestsDependencyWarning)

# Function to fetch license type from Go package URL
def fetch_go_license(lib, version):
    url = f"https://pkg.go.dev/{lib}@{version}"
    time.sleep(0.5)
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        license_tag = soup.find('a', {'data-test-id': 'UnitHeader-license'})
        return license_tag.text.strip() if license_tag else "不明"
    return "不明"

# Function to fetch license contents from Go package URL
def fetch_go_license_contents(lib, version):
    url = f"https://pkg.go.dev/{lib}@{version}?tab=licenses"
    time.sleep(0.5)
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        # Find the license contents
        license_contents_tag = soup.find('pre', {'class': 'License-contents'})
        license_contents = license_contents_tag.text.strip() if license_contents_tag else ""
        return license_contents
    return ""

# Function to fetch license type from React package URL
def fetch_react_license(lib):
    url = f"https://www.npmjs.com/package/{lib}"
    time.sleep(0.5)
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        # Find the main element
        main_div = soup.find('main', id='main')
        if main_div:
            # Look for the header that contains the text "License"
            license_header = main_div.find('h3', string="License")
            if license_header:
                # Get the next sibling <p> tag containing the license type
                license_paragraph = license_header.find_next_sibling('p')
                if license_paragraph:
                    return license_paragraph.text.strip()
    return "不明"

# Function to fetch license content from a React package
def fetch_react_license_content(lib):
    # Step 1: Retrieve the GitHub URL from the npm package page
    url = f"https://www.npmjs.com/package/{lib}"
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        github_link = soup.find('span', id='repository-link')
        if github_link:
            github_url = github_link.text.strip()
            # Extract the username and repository name
            path_parts = github_url.split('/')
            if len(path_parts) >= 3:
                username = path_parts[1]
                repo_name = path_parts[2]
                # Step 2: Construct potential license URLs
                license_urls = [
                    f"https://github.com/{username}/{repo_name}/blob/main/LICENSE",
                    f"https://github.com/{username}/{repo_name}/blob/main/LICENSE.md",
                    f"https://github.com/{username}/{repo_name}/blob/master/LICENSE",
                    f"https://github.com/{username}/{repo_name}/blob/master/LICENSE.md"
                ]
                # Check which URL is valid
                for license_url in license_urls:
                    # Construct the raw URL
                    if "blob/" in license_url:
                        raw_url = license_url.replace('github.com/', 'raw.githubusercontent.com/').replace('blob/', 'refs/heads/')
                        response = requests.get(raw_url)
                        if response.status_code == 200:
                            return response.text.strip()  # Return license content
    return ""

# Function to read package.json
def read_package_json(file_path):
    with open(file_path, 'r') as f:
        data = json.load(f)

    oss_list = []
    for lib, version in data.get('dependencies', {}).items():
        clean_version = version.lstrip('^')
        license_type = fetch_react_license(lib)
        license_content = fetch_react_license_content(lib)
        oss_list.append({
            "libName": lib,
            "libUrl": f"https://www.npmjs.com/package/{lib}",
            "version": clean_version,
            "license": license_type,
            "licenseContents": license_content,
        })
    return oss_list

# Function to read go.mod
def read_go_mod(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # Find all require statements, whether single line or block format
    modules = re.findall(r'^\s*require\s*\(\s*([^()]*?)\s*\)|^\s*require\s+([^\s]+)\s+([^\s]+)', content, re.MULTILINE | re.DOTALL)
    oss_list = []

    for module_block in modules:
        # Check if it's a block format
        if module_block[0]:  # Block format
            for line in module_block[0].strip().splitlines():
                line = line.strip()
                if line and not line.startswith('//'):
                    match = re.match(r'^\s*([^\s]+)\s+([^\s]+)', line)
                    if match:
                        lib, version = match.groups()
                        license_type = fetch_go_license(lib, version)
                        license_contents = fetch_go_license_contents(lib, version)
                        oss_list.append({
                            "libName": lib,
                            "libUrl": f"https://pkg.go.dev/{lib}@{version}",
                            "version": version,
                            "license": license_type,
                            "licenseContents": license_contents,
                        })
        else:  # Single line format
            lib = module_block[1]
            version = module_block[2]
            license_type = fetch_go_license(lib, version)
            license_contents = fetch_go_license_contents(lib, version)
            oss_list.append({
                "libName": lib,
                "libUrl": f"https://pkg.go.dev/{lib}@{version}",
                "version": version,
                "license": license_type,
                "licenseContents": license_contents,
            })

    return oss_list

# Function to export OSS list to CSV
def export_to_csv(oss_list, output_file):
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ["番号", "ライブラリー", "URL", "バージョン", "ライセンス", "ライセンス内容"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for index, item in enumerate(oss_list, start=1):
            writer.writerow({
                fieldnames[0]: index,
                fieldnames[1]: item['libName'],
                fieldnames[2]: item['libUrl'],
                fieldnames[3]: item['version'],
                fieldnames[4]: item['license'],
                fieldnames[5]: item['licenseContents']
            })

# Main function to select directory and process files
def select_directory():
    directory = filedialog.askdirectory()
    if not directory:
        return
    
    package_json_path = os.path.join(directory, 'package.json')
    go_mod_path = os.path.join(directory, 'go.mod')
    
    oss_list = []
    
    if os.path.exists(package_json_path):
        # Change button text to "出力中..."
        btn_select.config(text="出力中...")
        btn_select.update()
        oss_list = read_package_json(package_json_path)
    elif os.path.exists(go_mod_path):
        # Change button text to "出力中..."
        btn_select.config(text="出力中...")
        btn_select.update()
        oss_list = read_go_mod(go_mod_path)
    else:
        messagebox.showerror("Error", "選択したディレクトリに package.json または go.mod が見つかりません。")
        return

    # Automatically save the output CSV file in the selected directory
    output_file = os.path.join(directory, 'oss_list.csv')

    # Export the OSS list to CSV
    export_to_csv(oss_list, output_file)

    # Change button text back to original after processing
    btn_select.config(text="プロジェクトディレクトリを選択してください")
    btn_select.update()

    messagebox.showinfo("Success", f"OSS一覧ファイルの出力先は下記です。\n{output_file}")

    # Open the directory containing the output file
    open_directory(directory)

def open_directory(directory):
    # Check the operating system
    if os.name == 'nt':  # For Windows
        subprocess.Popen(f'explorer "{directory}"')
    elif os.name == 'posix':  # For macOS and Linux
        subprocess.Popen(['open', directory])

# Set up the GUI
root = tk.Tk()
root.title("プロジェクトのOSS一覧を出力するツール")

# Set the fixed size of the window (width x height)
root.geometry("400x100")

# Make the window non-resizable
root.resizable(False, False)

btn_select = tk.Button(root, text="プロジェクトディレクトリを選択してください", command=select_directory)
btn_select.pack(pady=20)

# Add the label at the bottom right
# Get the current year
current_year = datetime.now().year
label = tk.Label(root, text=f"Created by startiasoft\u00A9{current_year}")
label.place(relx=1.0, rely=1.0, anchor='se', x=-10, y=-5)

root.mainloop()
