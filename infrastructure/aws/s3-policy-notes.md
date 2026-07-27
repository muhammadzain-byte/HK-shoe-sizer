# S3 Security Notes

Use a private bucket. Do not allow public reads.

Object keys should be scoped by user:

```text
users/{user_id}/uploads/{image_id}.jpg
```

The application should grant only the operations it needs:

- `s3:PutObject`
- `s3:GetObject`
- `s3:AbortMultipartUpload`

Prefer IAM roles attached to the EC2 instance. Avoid long-lived static credentials in production.
