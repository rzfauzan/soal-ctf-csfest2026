big_alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
small_alphabet = "abcdefghijklmnopqrstuvwxyz"
possible_flag_printable = "{}_?!@"

ciphertext = "CTH?mso?axkw_xfxfkg?jvhflf!hcptftn@"

flag = ""
for i in range(len(ciphertext)):
    c = ciphertext[i]
    if c in big_alphabet:
        flag += big_alphabet[(big_alphabet.index(c) - i) % len(big_alphabet)]
    elif c in small_alphabet:
        flag += small_alphabet[(small_alphabet.index(c) - i) % len(small_alphabet)]
    else:
        flag += possible_flag_printable[(possible_flag_printable.index(c) - i) % len(possible_flag_printable)]

print("Recovered Flag:", flag)
