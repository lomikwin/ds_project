import requests

s = requests.Session()
url = "https://www.opinet.co.kr/user/opdown/opDownload.do"
payload = {
    "netfunnel_key": "",
    "opinet_key": "6qdFLpmi7zDOTaXPM8sWPCH2brugOXBbGUOD5s2BzzQ=",
}

r = s.post(url,data=payload,timeout=15)

print("status:",r.status_code)
print("len  :",len(r.text))
print("cookie",s.cookies.get_dict())