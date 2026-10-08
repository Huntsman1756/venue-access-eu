import { FirmView } from "@/components/firm-view";

export const instant = false;

export default async function FirmPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <FirmView id={decodeURIComponent(id)} />;
}
