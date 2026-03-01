import os
import subprocess

# 출력 디렉토리 설정
OUTPUT_DIR = "./certs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

#리눅스 환경에서 주석처리
#아래 run 호출도 리눅스 환경에 맞게 두세줄 수정해야함
OPENSSL_CNF = os.path.abspath("openssl.cnf")

# 파일 경로 정의
#사설 CA로써 자체적인 CA 공개키, 개인키를 새성하고 서버(MQTT)가 사용할 서버의 공개키, 개인키 생성 후 공개키 서명
#새 프로세스 생성 후 cmd로 openssl 호출
ca_key = os.path.join(OUTPUT_DIR, "ca.key")
ca_crt = os.path.join(OUTPUT_DIR, "ca.crt") 
server_key = os.path.join(OUTPUT_DIR, "server.key")
server_csr = os.path.join(OUTPUT_DIR, "server.csr")
server_crt = os.path.join(OUTPUT_DIR, "server.crt")
ca_srl = os.path.join(OUTPUT_DIR, "ca.srl")

# 명령어 실행 함수
def run(cmd, desc):
    print(f"[+] {desc} ...")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        raise RuntimeError(f"[-] Failed at: {desc}")

# 1. 사설 CA 키 생성
run(f"openssl genrsa -out {ca_key} 2048", "Generating CA private key")

# 2. 사설 CA 인증서 생성 (자체 서명)
run(f"openssl req -x509 -new -nodes -key {ca_key} "
    f"-days 3650 -out {ca_crt} -config {OPENSSL_CNF} -extensions v3_ca", "Creating CA certificate")

# 3. 서버 키 생성
run(f"openssl genrsa -out {server_key} 2048", "Generating server private key")

# 4. 서버 CSR 생성 (SAN 포함)
run(f"openssl req -new -key {server_key} -out {server_csr} "
    f"-config {OPENSSL_CNF} -extensions v3_req", "Creating server CSR with SAN")

# 5. 서버 인증서 발급 (CA 서명 + SAN 유지)
run(f"openssl x509 -req -in {server_csr} -CA {ca_crt} -CAkey {ca_key} -CAcreateserial "
    f"-out {server_crt} -days 3650 -sha256 "
    f"-extfile {OPENSSL_CNF} -extensions v3_req", "Signing server certificate with CA")

# 확인
print("\n[✔] 모든 인증서와 키 생성 완료!")
print(f"📂 인증서 위치: {os.path.abspath(OUTPUT_DIR)}")
print("\n생성된 파일 목록:")
for f in os.listdir(OUTPUT_DIR):
    print(f" - {f}")