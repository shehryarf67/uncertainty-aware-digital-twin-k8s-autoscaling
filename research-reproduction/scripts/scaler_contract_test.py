"""Execute actual author gRPC methods with a local mock Prometheus only.
These are interface tests, never Kubernetes or workload performance claims.
"""
from pathlib import Path
import os, sys, json, time, threading, importlib.util, argparse
from http.server import HTTPServer,BaseHTTPRequestHandler
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--run-id',default='run-02');args=parser.parse_args()
work=ROOT/'kubernetes-autoscaling'/'runtime-scaler'
os.environ.update(TF_NUM_INTRAOP_THREADS='4',TF_NUM_INTEROP_THREADS='2',OMP_NUM_THREADS='4')
os.chdir(work);sys.path.insert(0,str(work))
import grpc
import externalscaler_pb2 as pb
import externalscaler_pb2_grpc as rpc
from concurrent.futures import ThreadPoolExecutor
class Prom(BaseHTTPRequestHandler):
    rps=0
    def do_GET(self):
        data={'status':'success','data':{'resultType':'vector','result':[{'metric':{},'value':[time.time(),str(self.rps)]}]}}
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(data).encode())
    def log_message(self,*a):pass
mock=HTTPServer(('127.0.0.1',0),Prom);threading.Thread(target=mock.serve_forever,daemon=True).start()
spec=importlib.util.spec_from_file_location('author_scaler',work/'keda-grpc-server.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
server=grpc.server(ThreadPoolExecutor(max_workers=1));rpc.add_ExternalScalerServicer_to_server(module.ExternalScalerServicer(),server)
port=server.add_insecure_port('127.0.0.1:0');server.start()
channel=grpc.insecure_channel(f'127.0.0.1:{port}');stub=rpc.ExternalScalerStub(channel)
ref=pb.ScaledObjectRef(name='contract-test',namespace='local',scalerMetadata={'serverAddress':f'http://127.0.0.1:{mock.server_port}','query':'sum(rate(http_server_requests_seconds_count[1m]))','podLimit':'1000','scaleFactor':'100','activationValue':'10'})
records=[]
for name,rates in {'stable':[5,5,5,5],'increasing':[2,10,20,40],'spike':[5,5,50,5],'decreasing':[40,20,10,2]}.items():
    for rate in rates:
        Prom.rps=rate;start=time.perf_counter()
        try:
            response=stub.GetMetrics(pb.GetMetricsRequest(scaledObjectRef=ref,metricName='custom_metric'),timeout=30)
            metric=response.metricValues[0]
            records.append({'scenario':name,'mock_rps':rate,'metric_float':metric.metricValueFloat,'metric_int':metric.metricValue,'elapsed_ms':(time.perf_counter()-start)*1000,'status':'success'})
        except Exception as e:records.append({'scenario':name,'mock_rps':rate,'status':'failed','error':str(e)})
out=ROOT/'kubernetes-autoscaling'/'results';out.mkdir(exist_ok=True)
target=out/f'contract-test-{args.run_id}.json'
if target.exists():raise FileExistsError(target)
target.write_text(json.dumps({'scope':'real author-model inference and real gRPC; mocked Prometheus; no cluster scaling',
    'is_active':stub.IsActive(ref).result,'target':stub.GetMetricSpec(ref).metricSpecs[0].targetSizeFloat,'records':records},indent=2))
server.stop(0);channel.close();mock.shutdown();module.conn.close()
print(json.dumps(records,indent=2))
