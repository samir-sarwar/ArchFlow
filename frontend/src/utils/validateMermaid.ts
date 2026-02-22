export async function validateMermaidSyntax(
  syntax: string,
): Promise<{ valid: boolean; error?: string }> {
  try {
    const mermaid = (await import('mermaid')).default;
    mermaid.initialize({ startOnLoad: false });
    await mermaid.parse(syntax);
    return { valid: true };
  } catch (error) {
    return {
      valid: false,
      error: error instanceof Error ? error.message : 'Invalid syntax',
    };
  }
}
