"use client";

import { SearchExcerpt } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import ConfidenceBadge from "./ConfidenceBadge";
import SourceCitation from "./SourceCitation";

interface ResponsePackageCardProps {
  title: string;
  excerpts: SearchExcerpt[];
  confidence: number;
  routing: "answer" | "partial" | "no_answer";
}

export default function ResponsePackageCard({
  title,
  excerpts,
  confidence,
  routing,
}: ResponsePackageCardProps) {
  if (routing === "no_answer" || excerpts.length === 0) {
    return (
      <Card className="max-w-4xl mx-auto mt-8">
        <CardContent className="pt-8 pb-6 text-center">
          <CardTitle className="text-lg font-semibold text-foreground mb-2">
            No Answer Found
          </CardTitle>
          <p className="text-muted-foreground">
            I couldn&apos;t find information matching your query in the knowledge
            base. Try rephrasing or asking about a different topic.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="max-w-4xl mx-auto mt-8">
      <CardHeader>
        <div className="flex items-start justify-between">
          <CardTitle className="text-2xl text-foreground">{title}</CardTitle>
          <ConfidenceBadge confidence={confidence} routing={routing} />
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {excerpts.map((excerpt, i) => (
          <Card key={i} className="border border-border">
            <CardContent className="pt-4">
              <p className="text-sm leading-relaxed text-foreground whitespace-pre-line">
                {excerpt.text}
              </p>

              {excerpt.source.chunk_type === "table" && (
                <Badge variant="outline" className="mt-3">
                  Table excerpt
                </Badge>
              )}

              <Separator className="my-3" />

              <SourceCitation
                title={excerpt.source.title}
                section={excerpt.source.section}
                chunkType={excerpt.source.chunk_type}
              />
            </CardContent>
          </Card>
        ))}
      </CardContent>
    </Card>
  );
}
