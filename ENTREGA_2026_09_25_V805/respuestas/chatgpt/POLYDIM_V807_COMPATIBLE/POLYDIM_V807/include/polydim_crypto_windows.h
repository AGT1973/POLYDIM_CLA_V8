#pragma once
#ifdef _WIN32
#include <windows.h>
#include <bcrypt.h>
#include <vector>
#include <cstdint>
namespace polydim { namespace crypto {
// Windows-only optional C++ interface, NOT the stable C ABI.
// Caller must ensure unique 12-byte nonce per key across process restarts.
// Does not establish a PMTP security boundary by itself.
bool hmac_sha256(const std::vector<uint8_t>& key,const std::vector<uint8_t>& data,std::vector<uint8_t>& mac) noexcept;
bool aead_encrypt(const std::vector<uint8_t>& key,const std::vector<uint8_t>& nonce,const std::vector<uint8_t>& data,const std::vector<uint8_t>& ad,std::vector<uint8_t>& cipher,std::vector<uint8_t>& tag) noexcept;
bool aead_decrypt(const std::vector<uint8_t>& key,const std::vector<uint8_t>& nonce,const std::vector<uint8_t>& cipher,const std::vector<uint8_t>& tag,const std::vector<uint8_t>& ad,std::vector<uint8_t>& plain) noexcept;
SECURITY_ATTRIBUTES* secure_attributes() noexcept;
void free_secure_attributes(SECURITY_ATTRIBUTES*) noexcept;
}}
#endif
