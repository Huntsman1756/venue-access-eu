import type { Metadata } from "next";
import { HomeStats } from "@/components/home-stats";
import { SearchBar } from "@/components/search-bar";

export const metadata: Metadata = {
  title: "European venue membership, with evidence",
};

export default function Home() {
  return (
    <div className="flex flex-col items-center pt-14">
      <div className="w-full max-w-2xl text-center">
        <h1 className="font-mono text-3xl font-bold tracking-tight sm:text-4xl">
          European venue membership,
          <br />
          <span className="text-accent">with evidence.</span>
        </h1>
        <p className="mt-3 text-sm text-muted-foreground">
          Search firms, venues and observed membership history across European
          markets. Every claim links back to its captured public source.
        </p>
        <div className="mt-6">
          <SearchBar large autoFocus />
        </div>
      </div>
      <HomeStats />
      <section className="mt-12 w-full max-w-2xl rounded-md border border-border bg-card p-4 text-xs leading-relaxed text-muted-foreground">
        <p>
          <strong className="text-foreground">What “observed” means:</strong> a
          firm is OBSERVED on a venue when a captured, successfully processed
          official source lists it as a member. NOT_OBSERVED means no matching
          membership was found in that source — it does not prove absence of
          direct or indirect market access.
        </p>
      </section>
    </div>
  );
}
