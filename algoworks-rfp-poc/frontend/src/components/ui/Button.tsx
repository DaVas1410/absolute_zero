import type { ButtonHTMLAttributes, ReactNode } from 'react'
import './Button.css'

type ButtonWeight = 'primary' | 'secondary' | 'ghost'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  weight?: ButtonWeight
  icon?: ReactNode
}

export function Button({ weight = 'primary', icon, className, children, ...rest }: ButtonProps) {
  const classes = ['td-button', `td-button--${weight}`, className].filter(Boolean).join(' ')
  return (
    <button className={classes} {...rest}>
      {icon}
      {children}
    </button>
  )
}
