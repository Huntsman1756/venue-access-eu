import { VenueView } from "@/components/venue-view";

export const instant = false;

export default async function VenuePage({
  params,
}: {
  params: Promise<{ mic: string }>;
}) {
  const { mic } = await params;
  return <VenueView mic={mic.toUpperCase()} />;
}
