export default function ThreadsPage() {
  return (
    <div className="flex h-full min-h-0 items-center justify-center bg-background px-4">
      <div className="mx-auto max-w-md text-center">
        <h1 className="text-base font-semibold text-foreground">Select a thread to view</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Pick a thread from the left sidebar to open live activity, status, and controls.
        </p>
      </div>
    </div>
  );
}
