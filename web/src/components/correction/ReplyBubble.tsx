export default function ReplyBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] whitespace-pre-wrap rounded-xl border border-[#dee2e6] bg-white px-4 py-2.5 text-[#343a40] md:max-w-[70%]">
        {content}
      </div>
    </div>
  )
}
