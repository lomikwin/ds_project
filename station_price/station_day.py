import requests
import urllib

s = requests.Session()
url = "https://www.opinet.co.kr/user/opdown/opDownload.do"
payload = {
    "netfunnel_key": "",
    "opinet_key": "6qdFLpmi7zDOTaXPM8sWPCH2brugOXBbGUOD5s2BzzQ=",
}

r = s.post(url,data=payload,timeout=15)

nfl_url = ("https://nfl.opinet.co.kr/ts.wseq"
           "?opcode=5101&nfid=0&prefix=NetFunnel.gRtype=5101;"
           "&sid=service_1&aid=B7&js=yes")

r2 = s.get(nfl_url, timeout=15)
r2_chunk = r2.text.split('result=')[1].split("'")[1].split(":",2)
status_code =r2_chunk[0]
waiting_code =r2_chunk[1]
query_string =r2_chunk[2]
print("status_code:", status_code)
print("waiting_code:", waiting_code)
print("query_string:", query_string)
