import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import { type ReactNode } from 'react'

export function TooltipProvider({ children }: { children: ReactNode }) {
    return (
        <TooltipPrimitive.Provider delayDuration={0}>
            {children}
        </TooltipPrimitive.Provider>
    )
}

export function Tooltip({
    children,
    content,
}: {
    children: ReactNode
    content: ReactNode
}) {
    return (
        <TooltipPrimitive.Root>
            <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
            <TooltipPrimitive.Portal>
                <TooltipPrimitive.Content
                    side="top"
                    sideOffset={8}
                    className="z-50 max-w-[260px] rounded-lg border border-white/10 bg-zinc-900/95 px-3 py-2 text-xs text-zinc-100 shadow-xl backdrop-blur animate-in fade-in-0 zoom-in-95"
                >
                    {content}
                    <TooltipPrimitive.Arrow className="fill-zinc-900/95" />
                </TooltipPrimitive.Content>
            </TooltipPrimitive.Portal>
        </TooltipPrimitive.Root>
    )
}
