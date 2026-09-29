#ifndef POLYDIM_CRYPTO_V805_H
#define POLYDIM_CRYPTO_V805_H

#include <cstdint>
#include <vector>
#include <string>
#include <windows.h>
#include <bcrypt.h>

namespace polydim {
namespace crypto {

// G-1: HMAC-SHA256 namespace isolation
bool polydim_hmac_sha256(const std::vector<uint8_t>& key, const std::vector<uint8_t>& data, std::vector<uint8_t>& out_mac);

// G-2: AEAD Encryption for payloads (AES-GCM via Windows BCrypt)
bool polydim_aead_encrypt(const std::vector<uint8_t>& key, const std::vector<uint8_t>& nonce,
                          const std::vector<uint8_t>& data, const std::vector<uint8_t>& ad,
                          std::vector<uint8_t>& out_ciphertext, std::vector<uint8_t>& out_mac);

bool polydim_aead_decrypt(const std::vector<uint8_t>& key, const std::vector<uint8_t>& nonce,
                          const std::vector<uint8_t>& ciphertext, const std::vector<uint8_t>& mac,
                          const std::vector<uint8_t>& ad, std::vector<uint8_t>& out_plaintext);

// G-4, G-5: ACL/SID in Win32 and bInheritHandle = FALSE
SECURITY_ATTRIBUTES* get_secure_attributes();
void free_secure_attributes(SECURITY_ATTRIBUTES* sa);

} // namespace crypto
} // namespace polydim

#endif // POLYDIM_CRYPTO_V805_H
