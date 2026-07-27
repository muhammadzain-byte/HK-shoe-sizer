# External Foot Datasets

This area is for research datasets only. It is separate from the real-device validation dataset in `datasets/validation/`.

External datasets can help with segmentation research, landmark reasoning, surface normals, point clouds, and future 3D/depth experiments. They do not prove phone measurement accuracy.

Do not commit downloaded dataset files. Raw and processed payloads are ignored by `datasets/external/.gitignore`.

Use the manager script for safe inspection:

```powershell
python backend\scripts\external_dataset_manager.py list
python backend\scripts\external_dataset_manager.py print-download-instructions --dataset focus_synfoot2_foot3d
python backend\scripts\external_dataset_manager.py inspect --dataset focus_synfoot2_foot3d
python backend\scripts\external_dataset_manager.py manifest --dataset focus_synfoot2_foot3d
```

Downloads are manual or explicit only and require license review.
