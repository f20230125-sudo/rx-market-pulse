import type { Metadata } from "next";
import { Intelligence } from "@/components/Intelligence";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Commercial intelligence · Rx Market Pulse",
  description:
    "Ask questions about pharmaceutical spending, territory priorities and MSD pipeline evidence.",
};
export default function AskPage() {
  return <Intelligence mode={process.env.RX_AGENT_PROVIDER ?? "guided"} />;
}
