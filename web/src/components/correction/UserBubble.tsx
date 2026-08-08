export default function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] whitespace-pre-wrap rounded-xl bg-[#0ca678] px-4 py-2.5 text-white md:max-w-[70%]">
        {content}
      </div>
    </div>
  )
}
