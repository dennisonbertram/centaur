export default function ThreadDetailLoading() {
  return (
    <div className="flex h-full min-h-0 flex-col bg-background overflow-hidden">
      <div className="shrink-0 border-b border-border bg-background">
        <div className="mx-auto w-full max-w-[980px] px-5 py-3">
          <div className="flex items-center gap-2.5">
            <div className="h-4 w-4 rounded animate-shimmer" />
            <div className="h-5 w-16 rounded animate-shimmer" />
            <div className="size-[6px] rounded-full bg-muted" />
            <div className="h-3 w-12 rounded animate-shimmer" />
          </div>
        </div>
      </div>
      <div className="mx-auto flex-1 min-h-0 w-full max-w-[980px] space-y-3 px-5 py-4">
        <div className="h-3 w-full rounded animate-shimmer" />
        <div className="h-3 w-3/4 rounded animate-shimmer" />
        <div className="mt-2 h-8 w-full rounded-sm animate-shimmer" />
        <div className="h-8 w-full rounded-sm animate-shimmer" />
        <div className="mt-2 h-3 w-2/3 rounded animate-shimmer" />
        <div className="h-3 w-1/2 rounded animate-shimmer" />
      </div>
    </div>
  );
}
