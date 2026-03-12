import time
import redis
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Connexion Redis
r = redis.Redis(host='localhost', port=6379, db=0)

class ImageHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(('.png', '.jpg', '.jpeg')):
            print(f"Nouvelle image détectée : {event.src_path}")
            # On envoie le chemin vers la file d'attente
            r.lpush('image_queue', event.src_path)

if __name__ == "__main__":
    observer = Observer()
    handler = ImageHandler()
    observer.schedule(handler, path='../Data/catalog/', recursive=False)
    observer.start()
    
    print("Producer en écoute dans Catalog/...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()