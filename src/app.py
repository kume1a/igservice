import grpc
import urllib.request
import time
import os 

from pathlib import Path
from instagrapi import Client
from concurrent import futures

from proto import igservice_pb2, igservice_pb2_grpc

class IGServiceServicer(igservice_pb2_grpc.IGServiceServicer):
    def CreateIGTVVideo(self, request, context):
        ig_username = request.igUsername
        ig_password = request.igPassword
        video_url = request.videoURL
        title = request.title
        caption = request.caption
        thumbnail_url = request.thumbnailURL

        if not ig_username or not ig_password or not video_url \
           or not title or not caption or not thumbnail_url:
          print('Invalid request, missing parameters')

          context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
          context.set_details('Missing parameters')

          return igservice_pb2.CreateIGTVVideoResponse()

        try:
          video_path = f'upload/{time.time()}.mp4'
          thumbnail_path = f'upload/{time.time()}.jpg'

          urllib.request.urlretrieve(request.videoURL, video_path)
          urllib.request.urlretrieve(request.thumbnailURL,  thumbnail_path)

          cl = Client()
          success = cl.login(ig_username, ig_password)

          if not success:
            print('Invalid ig credentials, login failed')

            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details('Invalid ig credentials')

            return igservice_pb2.CreateIGTVVideoResponse()
          
          media = cl.igtv_upload(
            Path(video_path), 
            request.title, 
            request.caption,
            Path(thumbnail_path)
          )

          print(f'Media uploaded successfully!, id: {media.id}')

          os.remove(video_path)
          os.remove(thumbnail_path)

          return igservice_pb2.CreateIGTVVideoResponse(id=media.id)
        except Exception as e:
           print(e)

           context.set_code(grpc.StatusCode.INTERNAL)
           context.set_details(str(e))

           return igservice_pb2.CreateIGTVVideoResponse()

if __name__ == "__main__":
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))

    igservice_pb2_grpc.add_IGServiceServicer_to_server(IGServiceServicer(), server)

    port = os.getenv('PORT', 50051)

    server.add_insecure_port(f'[::]:{port}')
    server.start()

    print(f'Server started at port {port}')
    
    server.wait_for_termination()