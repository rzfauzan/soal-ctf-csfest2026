#!/usr/bin/env python3

import wave
import hashlib
import base64
import subprocess
import numpy as np
from pathlib import Path


class AudioForensics:
    
    @staticmethod
    def xor_decrypt(data: bytes, key: bytes) -> bytes:
        return bytes([data[i] ^ key[i % len(key)] for i in range(len(data))])
    
    @staticmethod
    def extract_lsb(audio_file: str) -> bytes:
        with wave.open(audio_file, 'rb') as wav:
            frames = wav.readframes(wav.getnframes())
            samples = np.frombuffer(frames, dtype=np.int16)
        
        binary = ''.join(str(sample & 1) for sample in samples)
        eof_marker = '1111111111111110'
        eof_pos = binary.find(eof_marker)
        
        if eof_pos == -1:
            print("[-] No EOF marker found")
            return None
        
        binary = binary[:eof_pos]
        extracted = bytearray()
        for i in range(0, len(binary), 8):
            if i + 8 <= len(binary):
                extracted.append(int(binary[i:i+8], 2))
        
        return bytes(extracted)
    
    @staticmethod
    def extract_metadata(audio_file: str) -> dict:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', audio_file],
            capture_output=True, text=True
        )
        
        if result.returncode != 0:
            return {}
        
        import json
        data = json.loads(result.stdout)
        
        if 'format' in data and 'tags' in data['format']:
            return {k.lower(): v for k, v in data['format']['tags'].items()}
        
        return {}


def solve_challenge(audio_file: str):
    
    print("=" * 60)
    print("Solver")
    print("=" * 60)
    print()
    
    flag_parts = []
    lsb_data = None
    
    print("[STEP 1] LSB Steganography Extraction")
    print("-" * 60)
    
    lsb_data = AudioForensics.extract_lsb(audio_file)
    
    if lsb_data:
        print(f"[+] Extracted {len(lsb_data)} bytes from LSB")
        
        if b"|XOR|" in lsb_data:
            parts = lsb_data.split(b"|XOR|")
            flag_parts.append(parts[0])
            print(f"[+] Flag Part 1: {parts[0].decode()}")
            print(f"[+] Found XOR encrypted data: {parts[1].hex()}")
            encrypted_part2 = parts[1]
        else:
            print("[-] No XOR delimiter found in LSB data")
            encrypted_part2 = None
    else:
        print("[-] Failed to extract LSB data")
        encrypted_part2 = None
    
    print()
    
    print("[STEP 2] Metadata Extraction")
    print("-" * 60)
    
    metadata = AudioForensics.extract_metadata(audio_file)
    
    xor_hint = None
    if 'encoder' in metadata:
        try:
            xor_hint = base64.b64decode(metadata['encoder']).decode()
            print(f"[+] XOR Hint (from encoder): {xor_hint}")
        except:
            pass
    
    for key in ['isft', 'software', 'encoder']:
        if key in metadata and not xor_hint:
            try:
                xor_hint = base64.b64decode(metadata[key]).decode()
                print(f"[+] XOR Hint (from {key}): {xor_hint}")
                break
            except:
                pass
    
    if xor_hint and encrypted_part2:
        xor_key = hashlib.md5(xor_hint.encode()).digest()[:8]
        print(f"[+] Generated XOR key: {xor_key.hex()}")
        decrypted = AudioForensics.xor_decrypt(encrypted_part2, xor_key)
        flag_parts.append(decrypted)
        print(f"[+] Flag Part 2: {decrypted.decode()}")
    elif encrypted_part2:
        print("[-] No XOR hint found, trying default...")
        xor_key = hashlib.md5(b"SPECTRAL_ANALYSIS_REQUIRED").digest()[:8]
        print(f"[+] Using default XOR key: {xor_key.hex()}")
        decrypted = AudioForensics.xor_decrypt(encrypted_part2, xor_key)
        flag_parts.append(decrypted)
        print(f"[+] Flag Part 2: {decrypted.decode()}")
    
    if 'comment' in metadata:
        try:
            decoded_comment = base64.b64decode(metadata['comment'])
            print(f"[+] Decoded comment: {decoded_comment}")
            flag_parts.append(decoded_comment)
            print(f"[+] Flag Parts 3+4: {decoded_comment.decode()}")
        except Exception as e:
            print(f"[-] Failed to decode comment: {e}")
    else:
        print("[-] No comment metadata found")
    
    print()
    
    # Final Result
    print("=" * 60)
    print("FINAL RESULT")
    print("=" * 60)
    
    if flag_parts:
        try:
            complete_flag = b''.join(flag_parts).decode('utf-8', errors='ignore')
            print(f"\nFLAG: {complete_flag}\n")
        except Exception as e:
            print(f"\n[-] Error decoding flag: {e}\n")
    else:
        print("\n[-] No flag parts found\n")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 solver.py <audio_file>")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    
    if not Path(audio_file).exists():
        print(f"Error: File '{audio_file}' not found")
        sys.exit(1)
    
    solve_challenge(audio_file)
