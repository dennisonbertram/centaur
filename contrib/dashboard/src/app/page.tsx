import Link from "next/link";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export default function Home() {
  return (
    <div className="space-y-10">
      <div className="space-y-2">
        <h1 className="text-2xl font-medium tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Manage your Centaur agent deployments.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Link href="/deployments">
          <Card className="h-full transition-all hover:shadow-lg hover:border-foreground/20 group">
            <CardHeader className="space-y-2">
              <CardTitle className="text-base font-medium group-hover:text-primary transition-colors">
                Deployments
              </CardTitle>
              <CardDescription className="text-sm leading-relaxed">
                Create, manage, and monitor your Centaur instances on Hetzner Cloud.
              </CardDescription>
            </CardHeader>
          </Card>
        </Link>

        <Link href="/usage">
          <Card className="h-full transition-all hover:shadow-lg hover:border-foreground/20 group">
            <CardHeader className="space-y-2">
              <CardTitle className="text-base font-medium group-hover:text-primary transition-colors">
                Usage
              </CardTitle>
              <CardDescription className="text-sm leading-relaxed">
                Track agent turns, tool invocations, and estimated monthly costs.
              </CardDescription>
            </CardHeader>
          </Card>
        </Link>
      </div>
    </div>
  );
}
