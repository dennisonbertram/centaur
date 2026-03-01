import {
  ThreadLayout,
  THREAD_SIDEBAR_COLLAPSE_CLASS,
  THREAD_SIDEBAR_COLLAPSE_STORAGE_KEY,
} from "@/components/thread/thread-layout";

const SIDEBAR_BOOTSTRAP_SCRIPT = `
(() => {
  try {
    var collapsed = window.localStorage.getItem("${THREAD_SIDEBAR_COLLAPSE_STORAGE_KEY}") === "1";
    document.documentElement.classList.toggle("${THREAD_SIDEBAR_COLLAPSE_CLASS}", collapsed);
  } catch (_) {}
})();
`;

export default function ThreadsLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <script dangerouslySetInnerHTML={{ __html: SIDEBAR_BOOTSTRAP_SCRIPT }} />
      <ThreadLayout>{children}</ThreadLayout>
    </>
  );
}
