export default function ChatThinkingMessage() {
  return (
    <div className="flex justify-start">
      <div
        data-testid="stream-thinking"
        className="w-full max-w-[60%] rounded-xl border border-[#dee2e6] bg-white px-4 py-3"
        aria-live="polite"
      >
        <p className="text-sm text-[#868e96]">思考中…</p>
        <div className="mt-3 space-y-2">
          <div className="h-3 w-4/5 animate-pulse rounded bg-[#e9ecef]" />
          <div className="h-3 w-3/5 animate-pulse rounded bg-[#e9ecef]" />
        </div>
      </div>
    </div>
  )
}
