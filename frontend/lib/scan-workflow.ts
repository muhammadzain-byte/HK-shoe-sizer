import {
  checkScanCaptureQuality,
  createScan,
  uploadLocalValidationImage,
} from "@/lib/api";
import type { CaptureQualityResult, CaptureQualityResponse, FootScan, FootSide, LocalUploadResponse } from "@/lib/types";

export type UploadScanImageResult = FootScan & {
  uploaded_image_id: string;
  upload: LocalUploadResponse;
  capture_quality: CaptureQualityResult;
};

export type UploadScanImageOptions = {
  token: string;
  footSide: FootSide;
  file: Blob;
  fileName: string;
  onProgress: (progress: number) => void;
  onStage?: (stage: ScanUploadStage) => void;
};

export type ScanUploadStage =
  | "creating_scan"
  | "uploading_image"
  | "validating_capture"
  | "completed";

export async function uploadScanImage({
  token,
  footSide,
  file,
  fileName,
  onProgress,
  onStage,
}: UploadScanImageOptions): Promise<UploadScanImageResult> {
  onStage?.("creating_scan");
  const scan = await createScan(token, footSide);
  onProgress(25);
  onStage?.("uploading_image");
  const uploadFile =
    file instanceof File
      ? file
      : new File([file], fileName, { type: file.type || "image/jpeg" });
  const upload = await uploadLocalValidationImage(token, {
    file: uploadFile,
    footScanId: scan.id,
  });
  onProgress(70);
  onStage?.("validating_capture");
  const quality = unwrapCaptureQuality(
    await checkScanCaptureQuality(token, scan.id, {
      uploaded_image_id: upload.image_id,
    }),
  );
  onProgress(100);
  onStage?.("completed");

  return {
    ...scan,
    status: "image_uploaded",
    uploaded_image_id: upload.image_id,
    upload,
    capture_quality: quality,
  };
}

function unwrapCaptureQuality(response: CaptureQualityResponse): CaptureQualityResult {
  if ("capture_quality" in response) {
    return response.capture_quality;
  }
  return response;
}
