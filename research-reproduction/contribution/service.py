"""Controlled CPU service for a separate experiment; author app is unchanged."""
import hashlib,json,os,threading,time,urllib.parse
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
START=time.monotonic();LOCK=threading.Semaphore(1)
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        parsed=urllib.parse.urlparse(self.path)
        if parsed.path=='/health':
            code=200 if time.monotonic()-START>=float(os.getenv('STARTUP_DELAY','5')) else 503
            return self.reply(code,{'ready':code==200})
        if parsed.path!='/work':return self.reply(404,{})
        units=max(.25,min(3,float(urllib.parse.parse_qs(parsed.query).get('units',['1'])[0])))
        wait=time.monotonic()
        if not LOCK.acquire(timeout=2):return self.reply(429,{'pod':os.getenv('HOSTNAME'),'rejected':True})
        try:
            begin=time.thread_time();wall=time.monotonic()
            hashlib.pbkdf2_hmac('sha256',b'cloud-research',b'fixed-salt',int(100000*units))
            cpu=(time.thread_time()-begin)*1000
            self.reply(200,{'pod':os.getenv('HOSTNAME'),'cpu_ms':cpu,'service_wall_ms':(time.monotonic()-wall)*1000,'queue_ms':(wall-wait)*1000})
        finally:LOCK.release()
    def reply(self,code,obj):
        data=json.dumps(obj).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers()
        try:self.wfile.write(data)
        except (BrokenPipeError,ConnectionResetError):pass
ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever()
