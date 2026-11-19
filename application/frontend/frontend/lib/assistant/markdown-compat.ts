/**
 * Compatibility boundary for the optional markdown rendering package.
 *
 * `unstable_memoizeMarkdownComponents` is still marked unstable upstream.
 * Presentation modules import the stable local alias instead.
 */
import { unstable_memoizeMarkdownComponents } from "@assistant-ui/react-markdown";

export const memoizeMarkdownComponents = unstable_memoizeMarkdownComponents;
