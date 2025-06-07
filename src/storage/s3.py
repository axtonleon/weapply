# import os
# import uuid
# import io
# import logging
# from minio import Minio
# from minio.error import S3Error
# from fastapi import UploadFile
# from starlette.concurrency import run_in_threadpool
# from src.core.config import settings

# # Configure logging
# logger = logging.getLogger(__name__)

# def get_minio_client() -> Minio:
#     """Initializes and returns the Minio client."""
#     logger.info(f"S3: Connecting to endpoint: {settings.S3_ENDPOINT_URL}")
#     logger.info(f"S3: Using access key: {settings.S3_ACCESS_KEY[:4]}...")

#     try:
#         # The Minio client endpoint should NOT include http:// or https://
#         endpoint = settings.S3_ENDPOINT_URL.replace("http://", "").replace("https://", "")
        
#         # Handle port logic more carefully
#         if ':' not in endpoint:
#             # Only add default port if not using standard AWS S3
#             if "amazonaws.com" not in endpoint:
#                 endpoint = f"{endpoint}:9000" if not settings.S3_SECURE else f"{endpoint}:443"
#                 logger.info(f"S3: Appending default port to endpoint: {endpoint}")

#         logger.info(f"S3: endpoint: {endpoint}, access_key: {settings.S3_ACCESS_KEY[:4]}..., "
#                    f"secret_key: {settings.S3_SECRET_KEY[:4]}..., secure: {settings.S3_SECURE}, "
#                    f"bucket_name: {settings.S3_BUCKET_NAME}")
        
#         client = Minio(
#             endpoint,
#             access_key=settings.S3_ACCESS_KEY,
#             secret_key=settings.S3_SECRET_KEY,
#             secure=settings.S3_SECURE
#         )

#         # Check if the bucket exists and create it if not
#         try:
#             found = client.bucket_exists(settings.S3_BUCKET_NAME)
#             if not found:
#                 logger.info(f"S3: Bucket '{settings.S3_BUCKET_NAME}' not found, creating...")
#                 client.make_bucket(settings.S3_BUCKET_NAME)
#                 logger.info(f"S3: Bucket '{settings.S3_BUCKET_NAME}' created.")
#             else:
#                 logger.info(f"S3: Bucket '{settings.S3_BUCKET_NAME}' already exists.")
#         except S3Error as e:
#             logger.error(f"S3 Error checking or creating bucket '{settings.S3_BUCKET_NAME}': {e}")
#             # For production, you might want to raise this error
#             # raise

#         return client

#     except S3Error as e:
#         logger.error(f"S3 Error initializing client: {e}")
#         raise
#     except Exception as e:
#         logger.error(f"Unexpected error initializing S3 client: {e}")
#         raise

# def upload_file_to_s3_sync(file_content: bytes, original_filename: str, user_id: int, bucket_name: str) -> str:
#     """
#     Synchronously uploads file content to S3 and returns the object name (key).
    
#     Args:
#         file_content: The byte content of the file.
#         original_filename: The original filename (for object naming).
#         user_id: The ID of the user uploading (for object path).
#         bucket_name: The S3 bucket name.
        
#     Returns:
#         The S3 object name (key) where the file was saved.
#     """
#     if not file_content:
#         raise ValueError("File content cannot be empty")
    
#     if not original_filename:
#         raise ValueError("Original filename cannot be empty")
    
#     client = get_minio_client()

#     # Generate a unique object name (key)
#     unique_id = uuid.uuid4().hex[:8]
    
#     # Sanitize filename more robustly
#     safe_filename = "".join([c for c in original_filename if c.isalnum() or c in ('.', '_', '-')]).rstrip('.')
    
#     # Ensure filename is not empty after sanitization
#     if not safe_filename:
#         file_ext = os.path.splitext(original_filename)[1] if original_filename else '.bin'
#         safe_filename = f"upload{file_ext}"

#     # Construct the full object name path within the bucket
#     object_name = f"user_{user_id}/{unique_id}_{safe_filename}"

#     # Use BytesIO to provide file-like object from bytes content
#     file_like_object = io.BytesIO(file_content)
#     content_length = len(file_content)

#     try:
#         logger.info(f"S3: Attempting to upload {object_name} to bucket {bucket_name} (size: {content_length} bytes)")
        
#         # Upload the object
#         client.put_object(
#             bucket_name,
#             object_name,
#             file_like_object,
#             content_length,
#             # You might want to detect and set content_type based on file extension
#             # content_type=detect_content_type(original_filename)
#         )
        
#         logger.info(f"S3: Successfully uploaded {object_name} to bucket {bucket_name}")
#         return object_name

#     except S3Error as e:
#         logger.error(f"S3 Error uploading file {object_name} to bucket {bucket_name}: {e}")
#         raise
#     except Exception as e:
#         logger.error(f"Unexpected error uploading file {object_name} to S3: {e}")
#         raise
#     finally:
#         # Ensure BytesIO is closed
#         file_like_object.close()

# def download_file_from_s3_sync(object_name: str, bucket_name: str) -> bytes | None:
#     """
#     Synchronously downloads a file's content from S3 and returns it as bytes.
    
#     Args:
#         object_name: The S3 object name (key).
#         bucket_name: The S3 bucket name.
        
#     Returns:
#         The file content as bytes, or None if the object is not found.
#     """
#     if not object_name:
#         raise ValueError("Object name cannot be empty")
    
#     client = get_minio_client()

#     try:
#         logger.info(f"S3: Attempting to download {object_name} from bucket {bucket_name}")
        
#         # Get the object
#         response = client.get_object(bucket_name, object_name)
        
#         try:
#             # Read the data
#             file_content = response.read()
#             logger.info(f"S3: Successfully downloaded {object_name} from bucket {bucket_name} (size: {len(file_content)} bytes)")
#             return file_content
#         finally:
#             # Always close the response stream and release connection
#             response.close()
#             response.release_conn()

#     except S3Error as e:
#         logger.error(f"S3 Error downloading file {object_name} from bucket {bucket_name}: {e}")
        
#         # Handle specific S3 errors
#         if e.code == "NoSuchKey":
#             logger.warning(f"S3: Object not found: {object_name} in bucket {bucket_name}")
#             return None
#         elif e.code == "NoSuchBucket":
#             logger.error(f"S3: Bucket not found: {bucket_name}")
#             raise ValueError(f"Bucket '{bucket_name}' does not exist")
#         else:
#             raise
            
#     except Exception as e:
#         logger.error(f"Unexpected error downloading file {object_name} from S3: {e}")
#         raise

# # Async wrappers for FastAPI
# async def upload_file_to_s3(file: UploadFile, user_id: int) -> str:
#     """Async wrapper to upload a file to S3."""
#     if not file.filename:
#         raise ValueError("File must have a filename")
    
#     # Read the file content asynchronously
#     file_content = await file.read()
    
#     if not file_content:
#         raise ValueError("File content is empty")
    
#     # Reset file pointer for potential future reads
#     await file.seek(0)
    
#     # Run the synchronous upload function in a threadpool
#     return await run_in_threadpool(
#         upload_file_to_s3_sync, 
#         file_content, 
#         file.filename, 
#         user_id, 
#         settings.S3_BUCKET_NAME
#     )

# async def download_file_from_s3(object_name: str) -> bytes | None:
#     """Async wrapper to download a file from S3."""
#     if not object_name:
#         raise ValueError("Object name cannot be empty")
    
#     # Run the synchronous download function in a threadpool
#     return await run_in_threadpool(
#         download_file_from_s3_sync, 
#         object_name, 
#         settings.S3_BUCKET_NAME
#     )

# # Optional: Helper function to check if object exists
# async def object_exists(object_name: str) -> bool:
#     """Check if an object exists in S3."""
#     def _check_exists(obj_name: str, bucket_name: str) -> bool:
#         client = get_minio_client()
#         try:
#             client.stat_object(bucket_name, obj_name)
#             return True
#         except S3Error as e:
#             if e.code == "NoSuchKey":
#                 return False
#             raise
    
#     return await run_in_threadpool(_check_exists, object_name, settings.S3_BUCKET_NAME)

# # Optional: Helper function to delete objects
# async def delete_file_from_s3(object_name: str) -> bool:
#     """Delete a file from S3."""
#     def _delete_file(obj_name: str, bucket_name: str) -> bool:
#         client = get_minio_client()
#         try:
#             client.remove_object(bucket_name, obj_name)
#             logger.info(f"S3: Successfully deleted {obj_name} from bucket {bucket_name}")
#             return True
#         except S3Error as e:
#             if e.code == "NoSuchKey":
#                 logger.warning(f"S3: Object not found for deletion: {obj_name}")
#                 return False
#             logger.error(f"S3 Error deleting file {obj_name}: {e}")
#             raise
    
#     return await run_in_threadpool(_delete_file, object_name, settings.S3_BUCKET_NAME)

# # Optional: Helper function to generate presigned URLs
# async def generate_presigned_url(object_name: str, expires_in_seconds: int = 3600) -> str:
#     """Generate a presigned URL for temporary access to an S3 object."""
#     def _generate_url(obj_name: str, bucket_name: str, expires: int) -> str:
#         from datetime import timedelta
#         client = get_minio_client()
#         try:
#             url = client.presigned_get_object(
#                 bucket_name, 
#                 obj_name, 
#                 expires=timedelta(seconds=expires)
#             )
#             logger.info(f"S3: Generated presigned URL for {obj_name} (expires in {expires}s)")
#             return url
#         except S3Error as e:
#             logger.error(f"S3 Error generating presigned URL for {obj_name}: {e}")
#             raise
    
#     return await run_in_threadpool(_generate_url, object_name, settings.S3_BUCKET_NAME, expires_in_seconds)

# # Optional: Helper function to detect content type
# def detect_content_type(filename: str) -> str:
#     """Detect content type based on file extension."""
#     import mimetypes
#     content_type, _ = mimetypes.guess_type(filename)
#     return content_type or 'application/octet-stream'