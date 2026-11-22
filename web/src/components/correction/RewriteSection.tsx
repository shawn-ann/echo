import type { RewriteOption, RewriteSection as RewriteSectionType } from '@/api/messages'
import RewriteBox from '@/components/correction/RewriteBox'

function optionProps(option: RewriteOption) {
  return { text: option.text, note: option.note }
}

export default function RewriteSection({
  rewrite,
  show = 'both',
}: {
  rewrite: RewriteSectionType
  show?: 'both' | 'natural-only'
}) {
  return (
    <div className="space-y-2">
      {show === 'both' && (
        <RewriteBox
          label="最小修正"
          icon="✏️"
          accent="text-[#2b8a3e]"
          {...optionProps(rewrite.minimal)}
        />
      )}
      <RewriteBox
        label="地道表达"
        icon="✨"
        accent="text-[#7048e8]"
        {...optionProps(rewrite.natural)}
      />
    </div>
  )
}
