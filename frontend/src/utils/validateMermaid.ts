export async function validateMermaidSyntax(
  syntax: string,
): Promise<{ valid: boolean; error?: string }> {
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const mermaid = (window as any).mermaid;
    if (!mermaid) throw new Error('Mermaid not loaded');
    await mermaid.parse(syntax);
    return { valid: true };
  } catch (error) {
    return {
      valid: false,
      error: error instanceof Error ? error.message : 'Invalid syntax',
    };
  }
}
