import * as React from 'react'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link' | 'amber' | 'brand-outline'
  size?: 'default' | 'sm' | 'lg' | 'xl' | 'icon'
  asChild?: boolean
}
export declare const Button: React.ForwardRefExoticComponent<ButtonProps & React.RefAttributes<HTMLButtonElement>>

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'secondary' | 'destructive' | 'outline' | 'green' | 'amber' | 'blue' | 'violet' | 'red' | 'muted' | 'model-gemma' | 'model-qwen'
}
export declare const Badge: React.ComponentType<BadgeProps>

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {}
export declare const Card: React.ComponentType<CardProps>
export interface CardHeaderProps extends React.HTMLAttributes<HTMLDivElement> {}
export declare const CardHeader: React.ComponentType<CardHeaderProps>
export interface CardFooterProps extends React.HTMLAttributes<HTMLDivElement> {}
export declare const CardFooter: React.ComponentType<CardFooterProps>
export interface CardTitleProps extends React.HTMLAttributes<HTMLHeadingElement> {}
export declare const CardTitle: React.ComponentType<CardTitleProps>
export interface CardDescriptionProps extends React.HTMLAttributes<HTMLParagraphElement> {}
export declare const CardDescription: React.ComponentType<CardDescriptionProps>
export interface CardContentProps extends React.HTMLAttributes<HTMLDivElement> {}
export declare const CardContent: React.ComponentType<CardContentProps>

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}
export declare const Input: React.ComponentType<InputProps>
export interface LabelProps extends React.LabelHTMLAttributes<HTMLLabelElement> {}
export declare const Label: React.ComponentType<LabelProps>
export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> { value?: number }
export declare const Progress: React.ComponentType<ProgressProps>
export interface ScrollAreaProps extends React.HTMLAttributes<HTMLDivElement> {}
export declare const ScrollArea: React.ComponentType<ScrollAreaProps>
export interface ScrollBarProps extends React.HTMLAttributes<HTMLDivElement> { orientation?: 'vertical' | 'horizontal' }
export declare const ScrollBar: React.ComponentType<ScrollBarProps>
export interface SeparatorProps extends React.HTMLAttributes<HTMLDivElement> { orientation?: 'horizontal' | 'vertical'; decorative?: boolean }
export declare const Separator: React.ComponentType<SeparatorProps>
export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}
export declare const Textarea: React.ComponentType<TextareaProps>
export interface AvatarProps extends React.HTMLAttributes<HTMLSpanElement> {}
export declare const Avatar: React.ComponentType<AvatarProps>
export interface AvatarImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {}
export declare const AvatarImage: React.ComponentType<AvatarImageProps>
export interface AvatarFallbackProps extends React.HTMLAttributes<HTMLSpanElement> {}
export declare const AvatarFallback: React.ComponentType<AvatarFallbackProps>

export interface SelectProps { value?: string; defaultValue?: string; onValueChange?: (value: string) => void; open?: boolean; defaultOpen?: boolean; children?: React.ReactNode }
export declare const Select: React.ComponentType<SelectProps>
export interface SelectGroupProps { children?: React.ReactNode }
export declare const SelectGroup: React.ComponentType<SelectGroupProps>
export interface SelectValueProps { placeholder?: string; children?: React.ReactNode }
export declare const SelectValue: React.ComponentType<SelectValueProps>
export interface SelectTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {}
export declare const SelectTrigger: React.ComponentType<SelectTriggerProps>
export interface SelectContentProps { children?: React.ReactNode; position?: 'item-aligned' | 'popper' }
export declare const SelectContent: React.ComponentType<SelectContentProps>
export interface SelectLabelProps { children?: React.ReactNode }
export declare const SelectLabel: React.ComponentType<SelectLabelProps>
export interface SelectItemProps { value: string; disabled?: boolean; children?: React.ReactNode }
export declare const SelectItem: React.ComponentType<SelectItemProps>
export interface SelectSeparatorProps {}
export declare const SelectSeparator: React.ComponentType<SelectSeparatorProps>
export interface SelectScrollUpButtonProps {}
export declare const SelectScrollUpButton: React.ComponentType<SelectScrollUpButtonProps>
export interface SelectScrollDownButtonProps {}
export declare const SelectScrollDownButton: React.ComponentType<SelectScrollDownButtonProps>

export interface TableProps extends React.TableHTMLAttributes<HTMLTableElement> {}
export declare const Table: React.ComponentType<TableProps>
export interface TableHeaderProps extends React.HTMLAttributes<HTMLTableSectionElement> {}
export declare const TableHeader: React.ComponentType<TableHeaderProps>
export interface TableBodyProps extends React.HTMLAttributes<HTMLTableSectionElement> {}
export declare const TableBody: React.ComponentType<TableBodyProps>
export interface TableFooterProps extends React.HTMLAttributes<HTMLTableSectionElement> {}
export declare const TableFooter: React.ComponentType<TableFooterProps>
export interface TableHeadProps extends React.ThHTMLAttributes<HTMLTableCellElement> {}
export declare const TableHead: React.ComponentType<TableHeadProps>
export interface TableRowProps extends React.HTMLAttributes<HTMLTableRowElement> {}
export declare const TableRow: React.ComponentType<TableRowProps>
export interface TableCellProps extends React.TdHTMLAttributes<HTMLTableCellElement> {}
export declare const TableCell: React.ComponentType<TableCellProps>
export interface TableCaptionProps extends React.HTMLAttributes<HTMLTableCaptionElement> {}
export declare const TableCaption: React.ComponentType<TableCaptionProps>

export interface AccountMenuProps { identity?: any; busy?: boolean; onLogin?: () => void; onLogout?: () => void; onLoadSessions?: () => Promise<any[]>; onRevokeSession?: (id: string) => void; onLinkZalo?: () => void; onOpenZaloOA?: () => void; onUnlinkZaloOA?: () => void }
export declare const AccountMenu: React.ComponentType<AccountMenuProps>
export interface AppRuntimeBoundaryProps { children?: React.ReactNode }
export declare const AppRuntimeBoundary: React.ComponentType<AppRuntimeBoundaryProps>
export interface AuthDialogProps { open?: boolean; busy?: boolean; error?: string; onClose?: () => void; onSubmit?: (data: any) => void; onStartZalo?: () => void }
export declare const AuthDialog: React.ComponentType<AuthDialogProps>
export interface AutopilotOutcomeProps { workspace?: any; taskByKey?: any; fallbackBrief?: any; reportState?: any; onReportChange?: (data: any) => void; onSendReportQuestion?: (text: string) => void; onReportActivate?: (orderId: string, options?: any) => Promise<void>; onReportExit?: () => void }
export declare const AutopilotOutcome: React.ComponentType<AutopilotOutcomeProps>
export interface AutopilotPanelProps { [key: string]: any }
export declare const AutopilotPanel: React.ComponentType<AutopilotPanelProps>
export interface AutopilotReviewProps { task: any; label?: string; brief?: any; formatPlan?: any; selectedPlacementIds?: string[]; onPlacementSelectionChange?: (ids: string[]) => void }
export declare const AutopilotReview: React.ComponentType<AutopilotReviewProps>
export interface ClaimConversationDialogProps { conversation?: any; busy?: boolean; error?: string; onCancel?: () => void; onConfirm?: () => void }
export declare const ClaimConversationDialog: React.ComponentType<ClaimConversationDialogProps>
export interface ConversationHistoryProps { open?: boolean; conversations?: any[]; loading?: boolean; error?: string; onClose?: () => void; onResume?: (id: string) => void; onArchive?: (id: string) => void; onDelete?: (item: any) => void }
export declare const ConversationHistory: React.ComponentType<ConversationHistoryProps>
export interface DeleteConversationDialogProps { open?: boolean; conversation?: any; deleteAll?: boolean; busy?: boolean; error?: string; onCancel?: () => void; onConfirm?: () => void }
export declare const DeleteConversationDialog: React.ComponentType<DeleteConversationDialogProps>
export interface ExperienceSelectorProps { onSelect: (mode: 'guided' | 'autopilot') => void; busy?: boolean; error?: string; conversations?: any[]; historyLoading?: boolean; historyError?: string; [key: string]: any }
export declare const ExperienceSelector: React.ComponentType<ExperienceSelectorProps>
export interface SplitDividerProps { direction?: 'horizontal' | 'vertical'; onDrag?: (delta: number) => void }
export declare const SplitDivider: React.ComponentType<SplitDividerProps>
export interface StrategySimulatorProps { value: any; busy?: boolean; canSelect?: boolean; selectionHint?: string; onSelect?: (id: string) => void }
export declare const StrategySimulator: React.ComponentType<StrategySimulatorProps>
export interface TargetingPanelProps { targeting?: Record<string, string[]>; onChange?: (value: any) => void; autoExpand?: boolean }
export declare const TargetingPanel: React.ComponentType<TargetingPanelProps>
export interface TopBarProps { [key: string]: any }
export declare const TopBar: React.ComponentType<TopBarProps>
export interface ZaloIconProps { className?: string }
export declare const ZaloIcon: React.ComponentType<ZaloIconProps>
export interface ZaloLinkDialogProps { open?: boolean; onClose?: () => void; onLinked?: (data: any) => void }
export declare const ZaloLinkDialog: React.ComponentType<ZaloLinkDialogProps>
export interface ZaloOACompanionProps { identity?: any; onOpenZaloOA?: () => void }
export declare const ZaloOACompanion: React.ComponentType<ZaloOACompanionProps>

export interface ChatPaneProps { messages?: any[]; busy?: boolean; currentStep?: number; onSend?: (text: string) => void; onBack?: () => void; onRetry?: () => void; canRetry?: boolean; policy?: any }
export declare const ChatPane: React.ComponentType<ChatPaneProps>
export interface ChatComposerProps { busy?: boolean; currentStep?: number; onSend?: (text: string) => void; onBack?: () => void; policy?: any }
export declare const ChatComposer: React.ComponentType<ChatComposerProps>
export interface ChatThreadProps { messages?: any[]; canRetry?: boolean; onRetry?: () => void; onSend?: (text: string) => void }
export declare const ChatThread: React.ComponentType<ChatThreadProps>
export interface MessageBubbleProps { message: any; showSuggestions?: boolean; showRetry?: boolean; onRetry?: () => void; onSend?: (text: string) => void; busy?: boolean }
export declare const MessageBubble: React.ComponentType<MessageBubbleProps>

export interface StepperProps { steps: any[]; currentStep: number; stepStatuses: string[]; onStepJump?: (index: number) => void }
export declare const Stepper: React.ComponentType<StepperProps>
export interface WorkFootProps { step: any; stepIndex: number; stepStatus: string; totalSteps: number; canApprove?: boolean; busy?: boolean; onApprove?: () => void; onBack?: () => void; onNext?: () => void }
export declare const WorkFoot: React.ComponentType<WorkFootProps>
export interface WorkspacePaneProps { [key: string]: any }
export declare const WorkspacePane: React.ComponentType<WorkspacePaneProps>

export interface BlockRendererProps { block: any }
export declare const BlockRenderer: React.ComponentType<BlockRendererProps>
export interface ChartBlockProps { block: any }
export declare const ChartBlock: React.ComponentType<ChartBlockProps>

export interface BriefStepProps { data: any; onChange?: (data: any) => void; isDone?: boolean }
export declare const BriefStep: React.ComponentType<BriefStepProps>
export interface AudienceStepProps { data: any; onChange?: (data: any) => void; isDone?: boolean; brief?: any; recoFromChat?: any; expandTargeting?: boolean }
export declare const AudienceStep: React.ComponentType<AudienceStepProps>
export interface CreativeStepProps { data: any; onChange?: (data: any) => void; isDone?: boolean; brief?: any; segment?: any; formatPlan?: any; autopilotMode?: boolean }
export declare const CreativeStep: React.ComponentType<CreativeStepProps>
export interface EmailStepProps { brief?: any; zones?: any[]; selectedZoneIds?: string[]; audiences?: any; data: any; onChange?: (data: any) => void; isDone?: boolean; formState?: any }
export declare const EmailStep: React.ComponentType<EmailStepProps>
export interface ReportStepProps { data: any; onChange?: (data: any) => void; isDone?: boolean; formState?: any; onSendChat?: (text: string) => void; onRetry?: () => void }
export declare const ReportStep: React.ComponentType<ReportStepProps>
export interface SetupStepProps { data: any; onChange?: (data: any) => void; brief?: any; creative?: any; segment?: any; isDone?: boolean; assignmentRepair?: boolean }
export declare const SetupStep: React.ComponentType<SetupStepProps>
export interface SuccessStepProps { brief?: any; zones?: any[]; selectedZoneIds?: string[]; audienceSize?: number; setup?: any; allZones?: any[]; recoZones?: any[]; order?: any; forecast?: any }
export declare const SuccessStep: React.ComponentType<SuccessStepProps>
export interface AdImageGeneratorProps { brief?: any; segment?: any; onAddToCreative?: (files: any[]) => void }
export declare const AdImageGenerator: React.ComponentType<AdImageGeneratorProps>
export interface ImageCropModalProps { src: string; targetW: number; targetH: number; label?: string; onConfirm?: (data: any) => void; onScale?: (data: any) => void; onCancel?: () => void }
export declare const ImageCropModal: React.ComponentType<ImageCropModalProps>
export interface ConfirmPhaseProps { data: any; onChange?: (data: any) => void; brief?: any; segment?: any; files?: any[]; allZones?: any[]; recoZones?: any[] }
export declare const ConfirmPhase: React.ComponentType<ConfirmPhaseProps>
export interface CreativeAssignPhaseProps { data: any; onChange?: (data: any) => void; files?: any[]; allZones?: any[]; recoZones?: any[]; repairMode?: boolean }
export declare const CreativeAssignPhase: React.ComponentType<CreativeAssignPhaseProps>
export interface ZoneSelectionPhaseProps { data: any; onChange?: (data: any) => void; brief?: any; allZones?: any[] }
export declare const ZoneSelectionPhase: React.ComponentType<ZoneSelectionPhaseProps>

export interface PublicLandingProps { onEnterAgent?: () => void; onOpenDemo?: (mode: 'copilot' | 'autopilot') => void }
export declare const PublicLanding: React.ComponentType<PublicLandingProps>
export interface LandingNavProps { onEnterAgent?: () => void; links?: Array<{ label: string; href: string }> }
export declare const LandingNav: React.ComponentType<LandingNavProps>
export interface LandingHeroProps { onEnterAgent?: () => void; onOpenDemo?: (mode: 'copilot' | 'autopilot') => void; title?: React.ReactNode }
export declare const LandingHero: React.ComponentType<LandingHeroProps>
export interface LandingPainProps {}
export declare const LandingPain: React.ComponentType<LandingPainProps>
export interface LandingHowItWorksProps {}
export declare const LandingHowItWorks: React.ComponentType<LandingHowItWorksProps>
export interface LandingModesProps { onEnterAgent?: () => void; onOpenDemo?: (mode: 'copilot' | 'autopilot') => void }
export declare const LandingModes: React.ComponentType<LandingModesProps>
export interface LandingProofProps {}
export declare const LandingProof: React.ComponentType<LandingProofProps>
export interface LandingFinalCtaProps { onEnterAgent?: () => void }
export declare const LandingFinalCta: React.ComponentType<LandingFinalCtaProps>
export interface LandingFooterProps { onEnterAgent?: () => void }
export declare const LandingFooter: React.ComponentType<LandingFooterProps>
