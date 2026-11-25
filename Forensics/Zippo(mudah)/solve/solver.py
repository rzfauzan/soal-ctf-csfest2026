#!/usr/bin/env python3
import zipfile
import os
import re

def solve_challenge(zip_path="build/challenge.zip"):
    current_zip = zip_path
    layer = 1
    
    os.makedirs("solve_temp", exist_ok=True)
    
    while True:
        print(f"[*] Extracting layer {layer}...")
        
        try:
            with zipfile.ZipFile(current_zip, 'r') as zf:
                zf.extractall("solve_temp")
            
            flag_path = "solve_temp/flag.txt"
            with open(flag_path, "rb") as f:
                content = f.read()
            
            flag_pattern = rb'ITECHNOCUP\{[^}]+\}'
            flags_found = re.findall(flag_pattern, content)
            
            if flags_found:
                for flag in flags_found:
                    flag_str = flag.decode('latin-1')
                    if "z1pp0_m4st3r" in flag_str:
                        print(f"\n[+] Real flag found at layer {layer}!")
                        print(f"[+] Flag: {flag_str}")
                        import shutil
                        shutil.rmtree("solve_temp")
                        print(f"\n[+] Challenge solved in {layer} layers!")
                        return
            
            pk_index = content.find(b'PK\x03\x04')
            if pk_index == -1:
                print(f"[-] No more layers found")
                break
            
            next_zip = f"solve_temp/layer_{layer+1}.zip"
            with open(next_zip, "wb") as f:
                f.write(content[pk_index:])
            
            current_zip = next_zip
            layer += 1
            
        except Exception as e:
            print(f"[-] Error: {e}")
            break
    
    import shutil
    shutil.rmtree("solve_temp")
    print(f"\n[+] Extraction completed at {layer} layers!")

if __name__ == "__main__":
    solve_challenge()
