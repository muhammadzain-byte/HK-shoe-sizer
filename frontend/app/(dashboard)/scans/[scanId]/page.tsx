import { ScanDetailView } from "@/components/scan-detail-view";

type ScanDetailPageProps = {
  params: Promise<{ scanId: string }>;
};

export default async function ScanDetailPage({ params }: ScanDetailPageProps) {
  const { scanId } = await params;
  return <ScanDetailView scanId={scanId} />;
}
