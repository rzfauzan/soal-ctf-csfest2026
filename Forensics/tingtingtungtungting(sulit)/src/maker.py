#!/usr/bin/env python3

import wave
import hashlib
import base64
import numpy as np
from pathlib import Path
import subprocess
import struct


class AudioSteganography:
    
    @staticmethod
    def xor_encrypt(data: bytes, key: bytes) -> bytes:
        """XOR encryption"""
        return bytes([data[i] ^ key[i % len(key)] for i in range(len(data))])
    
    @staticmethod
    def read_wav(filepath: str) -> tuple:
        with wave.open(filepath, 'rb') as wav:
            params = wav.getparams()
            frames = wav.readframes(params.nframes)
            samples = np.frombuffer(frames, dtype=np.int16)
            return params, samples
    
    @staticmethod
    def write_wav_with_metadata(filepath: str, params, samples: np.ndarray, metadata: dict):
        with wave.open(filepath, 'wb') as wav:
            wav.setparams(params)
            wav.writeframes(samples.astype(np.int16).tobytes())
        
        with open(filepath, 'r+b') as f:
            f.seek(0, 2)
            
            info_data = b''
            for key, value in metadata.items():
                key_bytes = key.encode('ascii')
                value_bytes = value.encode('utf-8') + b'\x00'
                if len(value_bytes) % 2:
                    value_bytes += b'\x00'
                chunk_size = len(value_bytes)
                info_data += key_bytes + struct.pack('<I', chunk_size) + value_bytes
            
            list_chunk = b'LIST' + struct.pack('<I', len(info_data) + 4) + b'INFO' + info_data
            
            f.seek(4)
            riff_size = struct.unpack('<I', f.read(4))[0]
            new_riff_size = riff_size + len(list_chunk)
            f.seek(4)
            f.write(struct.pack('<I', new_riff_size))
            
            f.seek(0, 2)
            f.write(list_chunk)
    
    @staticmethod
    def embed_lsb(samples: np.ndarray, data: bytes) -> np.ndarray:
        binary = ''.join(format(byte, '08b') for byte in data)
        binary += '1111111111111110'
        
        if len(binary) > len(samples):
            raise ValueError(f"Data too large: {len(binary)} bits > {len(samples)} samples")
        
        samples = samples.copy()
        for i, bit in enumerate(binary):
            samples[i] = (samples[i] & ~1) | int(bit)
        
        return samples


def create_challenge():
    
    print("[*] Creating multi-layer audio steganography challenge...")
    
    flag_parts = {
        'part1': b"CSF{pingpingpungpungping_",
        'part2': b"pingpingpungpungping_",
        'part3': b"haaaaaaaaaacchiiiiiimiiiiiiiii_",
        'part4': b"2026}"
    }
    
    xor_hint = "SPECTRAL_ANALYSIS_REQUIRED"
    xor_key = hashlib.md5(xor_hint.encode()).digest()[:8]
    
    encrypted_part2 = AudioSteganography.xor_encrypt(flag_parts['part2'], xor_key)
    lsb_data = flag_parts['part1'] + b"|XOR|" + encrypted_part2
    
    print(f"[*] LSB data: {lsb_data}")
    print(f"[*] LSB length: {len(lsb_data)} bytes")
    
    print("[*] Reading original audio file...")
    input_file = "uwaugh.mp3"
    
    temp_wav = "temp_input.wav"
    subprocess.run(['ffmpeg', '-i', input_file, '-ar', '44100', '-ac', '1', '-y', temp_wav],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    params, samples = AudioSteganography.read_wav(temp_wav)
    print(f"[*] Audio samples: {len(samples)}")
    
    print("[*] Embedding LSB steganography...")
    samples = AudioSteganography.embed_lsb(samples, lsb_data)
    
    print("[*] Adding metadata layers...")
    output_file = "challenge_final.wav"
    
    metadata = {
        'ICMT': base64.b64encode(flag_parts['part3'] + flag_parts['part4']).decode(),
        'INAM': 'The Sound of Secrets',
        'IART': 'Steganographer',
        'IPRD': 'Hidden Frequencies',
        'ISFT': base64.b64encode(xor_hint.encode()).decode()
    }
    
    AudioSteganography.write_wav_with_metadata(output_file, params, samples, metadata)
    
    Path(temp_wav).unlink(missing_ok=True)
    
    complete_flag = b''.join(flag_parts.values()).decode()
    
    print("\n[+] Challenge created successfully!")
    print(f"[+] Output file: {output_file}")
    print("\n[*] Challenge layers:")
    print("    1. LSB Steganography - Contains part1 + XOR encrypted part2")
    print("    2. Metadata ISFT - Base64 encoded XOR key hint")
    print("    3. Metadata ICMT - Base64 encoded part3 + part4")
    print(f"\n[*] Complete flag: {complete_flag}")
    print(f"[*] XOR Key (MD5 hash): {xor_key.hex()}")


if __name__ == "__main__":
    create_challenge()
