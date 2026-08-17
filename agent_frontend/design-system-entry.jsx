// Sync-only public surface for Claude Design. Re-export real application components.
export { Button } from './src/components/ui/button.jsx'
export { Badge } from './src/components/ui/badge.jsx'
export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent } from './src/components/ui/card.jsx'
export { Input } from './src/components/ui/input.jsx'
export { Label } from './src/components/ui/label.jsx'
export { Progress } from './src/components/ui/progress.jsx'
export { ScrollArea, ScrollBar } from './src/components/ui/scroll-area.jsx'
export {
  Select, SelectGroup, SelectValue, SelectTrigger, SelectContent,
  SelectLabel, SelectItem, SelectSeparator, SelectScrollUpButton, SelectScrollDownButton,
} from './src/components/ui/select.jsx'
export { Separator } from './src/components/ui/separator.jsx'
export {
  Table, TableHeader, TableBody, TableFooter, TableHead, TableRow, TableCell, TableCaption,
} from './src/components/ui/table.jsx'
export { Textarea } from './src/components/ui/textarea.jsx'
export { Avatar, AvatarImage, AvatarFallback } from './src/components/ui/avatar.jsx'

export { default as AccountMenu } from './src/components/AccountMenu.jsx'
export { default as AppRuntimeBoundary } from './src/components/AppRuntimeBoundary.jsx'
export { default as AuthDialog } from './src/components/AuthDialog.jsx'
export { default as AutopilotOutcome } from './src/components/AutopilotOutcome.jsx'
export { default as AutopilotPanel } from './src/components/AutopilotPanel.jsx'
export { default as AutopilotReview } from './src/components/AutopilotReview.jsx'
export { default as ClaimConversationDialog } from './src/components/ClaimConversationDialog.jsx'
export { default as ConversationHistory } from './src/components/ConversationHistory.jsx'
export { default as DeleteConversationDialog } from './src/components/DeleteConversationDialog.jsx'
export { default as ExperienceSelector } from './src/components/ExperienceSelector.jsx'
export { default as SplitDivider } from './src/components/SplitDivider.jsx'
export { default as StrategySimulator } from './src/components/StrategySimulator.jsx'
export { default as TargetingPanel } from './src/components/TargetingPanel.jsx'
export { default as TopBar } from './src/components/TopBar.jsx'
export { default as ZaloIcon } from './src/components/ZaloIcon.jsx'
export { default as ZaloLinkDialog } from './src/components/ZaloLinkDialog.jsx'
export { default as ZaloOACompanion } from './src/components/ZaloOACompanion.jsx'

export {
  default as PublicLanding,
  LandingNav, LandingHero, LandingPain, LandingHowItWorks,
  LandingModes, LandingProof, LandingFinalCta, LandingFooter,
} from './src/components/PublicLanding.jsx'

export { default as ChatPane } from './src/components/ChatPane/index.jsx'
export { default as ChatComposer } from './src/components/ChatPane/ChatComposer.jsx'
export { default as ChatThread } from './src/components/ChatPane/ChatThread.jsx'
export { default as MessageBubble } from './src/components/ChatPane/MessageBubble.jsx'

export { default as Stepper } from './src/components/WorkspacePane/Stepper.jsx'
export { default as WorkFoot } from './src/components/WorkspacePane/WorkFoot.jsx'
export { default as WorkspacePane } from './src/components/WorkspacePane/index.jsx'

export { default as BlockRenderer } from './src/blocks/BlockRenderer.jsx'
export { default as ChartBlock } from './src/blocks/ChartBlock.jsx'

export { default as BriefStep } from './src/steps/BriefStep.jsx'
export { default as AudienceStep } from './src/steps/AudienceStep.jsx'
export { default as CreativeStep } from './src/steps/CreativeStep.jsx'
export { default as EmailStep } from './src/steps/EmailStep.jsx'
export { default as ReportStep } from './src/steps/ReportStep.jsx'
export { default as SetupStep } from './src/steps/SetupStep.jsx'
export { default as SuccessStep } from './src/steps/SuccessStep.jsx'
export { default as AdImageGenerator } from './src/steps/creative/AdImageGenerator.jsx'
export { default as ImageCropModal } from './src/steps/creative/ImageCropModal.jsx'
export { default as ConfirmPhase } from './src/steps/setup/ConfirmPhase.jsx'
export { default as CreativeAssignPhase } from './src/steps/setup/CreativeAssignPhase.jsx'
export { default as ZoneSelectionPhase } from './src/steps/setup/ZoneSelectionPhase.jsx'
