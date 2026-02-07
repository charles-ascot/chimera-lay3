/**
 * CHIMERA v2 Status Badge
 */

interface Props {
  status: string
  className?: string
}

export default function StatusBadge({ status, className = '' }: Props) {
  const getClass = () => {
    switch (status.toUpperCase()) {
      case 'WON':
      case 'SUCCESS':
      case 'MATCHED':
      case 'OPEN':
      case 'STARTED':
        return 'badge-success'
      case 'LOST':
      case 'ERROR':
      case 'FAILURE':
      case 'CANCELLED':
        return 'badge-error'
      case 'PENDING':
      case 'UNMATCHED':
        return 'badge-warning'
      case 'IN-PLAY':
      case 'INPLAY':
        return 'badge-inplay'
      default:
        return 'badge-info'
    }
  }

  return (
    <span className={`${getClass()} ${className}`}>
      {status}
    </span>
  )
}
