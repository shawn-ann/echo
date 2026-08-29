import Composer from '@/components/correction/Composer'
import MessageList from '@/components/correction/MessageList'

export default function CorrectionPage() {
  return (
    <div className="flex h-full flex-col">
      <MessageList />
      <Composer />
    </div>
  )
}
