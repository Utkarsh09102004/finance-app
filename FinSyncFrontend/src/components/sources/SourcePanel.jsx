const SourcePanel = ({ sources }) => {
  if (!sources || sources.length === 0) {
    return <p className="text-sm text-muted-foreground">No sources captured yet.</p>;
  }

  return (
    <div className="space-y-4">
      {sources.map((source) => (
        <details key={source.id} className="rounded-2xl border bg-white/80 p-4 shadow" open>
          <summary className="cursor-pointer">
            <div className="flex flex-col">
              <span className="text-sm font-semibold text-foreground">{source.label}</span>
              <span className="text-xs text-muted-foreground">Tool: {source.tool}</span>
            </div>
          </summary>
          <div className="mt-4">
            <pre className="max-h-72 overflow-auto rounded-xl bg-muted/40 p-3 text-xs whitespace-pre-wrap break-all">
              {JSON.stringify(source.data, null, 2)}
            </pre>
          </div>
        </details>
      ))}
    </div>
  );
};

export default SourcePanel;
