export default function LoadingBubble({
  startedAt,
  now,
}: {
  startedAt: number | null
  now: number
}) {
  return (
    <div className="flex justify-start">
      <div className="rounded-xl border border-[#dee2e6] bg-white px-4 py-2.5 text-sm text-[#868e96]">
        思考中…
        {startedAt != null && (
          <span className="ml-2 text-xs">
            已用时 {((now - startedAt) / 1000).toFixed(1)}s
          </span>
        )}
      </div>
    </div>
  )
}
