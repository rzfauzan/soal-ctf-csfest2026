#!/usr/bin/env python3
import zipfile
import os
import random
import string

LAYERS = 67
FLAG = "CSF{z1pp0_m4st3r_unz1p_4ll_l4y3rs_67}"

def generate_noise(size=512):
    """Generate random binary noise"""
    return bytes(random.randint(0, 255) for _ in range(size))

def generate_honeypot_flag(layer):
    """Generate realistic looking honeypot flags"""
    fake_flags = [
        f"CSF{{apalah_aku_puh{layer:02d}}}",
        f"CSF{{modal_prompting_doang{layer:02d}}}",
        f"CSF{{yang_pake_ai_agent_dirodok_atmin{layer:02d}}}",
        f"CSF{{susu_bendera{layer:02d}}}",
        f"CSF{{SAYA_AKAN_LAWAN{layer:02d}}}",
    ]
    return random.choice(fake_flags)

def create_challenge():
    os.makedirs("build", exist_ok=True)
    random.seed(42)
    
    for i in range(LAYERS, 0, -1):
        if i == LAYERS:
            flag_content = FLAG.encode('latin-1')
        else:
            noise_before = generate_noise(random.randint(256, 512))
            honeypot = generate_honeypot_flag(i).encode('latin-1')
            noise_after = generate_noise(random.randint(128, 256))
            
            with open(f"build/layer_{i+1}.zip", "rb") as f:
                next_zip = f.read()
            
            flag_content = noise_before + honeypot + noise_after + next_zip
        
        with open("build/flag.txt", "wb") as f:
            f.write(flag_content)
        
        with zipfile.ZipFile(f"build/layer_{i}.zip", "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write("build/flag.txt", "flag.txt")
    
    os.rename("build/layer_1.zip", "build/challenge.zip")
    
    for i in range(2, LAYERS + 1):
        if os.path.exists(f"build/layer_{i}.zip"):
            os.remove(f"build/layer_{i}.zip")
    os.remove("build/flag.txt")
    
    print(f"[+] Challenge created: build/challenge.zip")
    print(f"[+] Layers: {LAYERS}")
    print(f"[+] Flag: {FLAG}")

if __name__ == "__main__":
    create_challenge()
