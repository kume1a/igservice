import grpc
import proto.igapi_pb2 as igapi_pb2
import proto.igapi_pb2_grpc as igapi_pb2_grpc

from concurrent import futures

class IGAPIServicer(igapi_pb2_grpc.IGAPIServicer):
    def CreateIGTVVideo(self, request, context):
        print(request)

        return igapi_pb2.CreateIGTVVideoResponse(id='1234')

if __name__ == "__main__":
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))

    igapi_pb2_grpc.add_IGAPIServicer_to_server(IGAPIServicer(), server)

    server.add_insecure_port('[::]:50051')
    server.start()
    server.wait_for_termination()