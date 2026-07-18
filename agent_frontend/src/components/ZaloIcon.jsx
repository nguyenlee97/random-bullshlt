export default function ZaloIcon({ className = 'h-5 w-5' }) {
  return (
    <svg
      viewBox="0 0 64 64"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M15.5 5.5h33A10.5 10.5 0 0 1 59 16v27a10.5 10.5 0 0 1-10.5 10.5H36.2L27 59l-8.7-5.5h-2.8A10.5 10.5 0 0 1 5 43V16A10.5 10.5 0 0 1 15.5 5.5Z"
        fill="#fff"
        stroke="#0068ff"
        strokeLinejoin="round"
        strokeWidth="5"
      />
      <text
        x="32"
        y="37.5"
        fill="#0068ff"
        fontFamily="Arial, sans-serif"
        fontSize="19"
        fontWeight="800"
        textAnchor="middle"
      >
        Zalo
      </text>
    </svg>
  )
}
