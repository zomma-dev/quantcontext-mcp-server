import { Nav } from "@/components/nav";
import { Hero } from "@/components/hero";
import { WhySection } from "@/components/why-section";
import { ToolsGrid } from "@/components/tools-grid";
import { ConversationDemo } from "@/components/conversation-demo";
import { PipelineDemo } from "@/components/pipeline-demo";
import { InstallSection } from "@/components/install-section";
import { HostedTeaser } from "@/components/hosted-teaser";
import { Footer } from "@/components/footer";

export default function Home() {
  return (
    <main className="min-h-screen bg-page">
      <Nav />
      <Hero />
      <WhySection />
      <ToolsGrid />
      <ConversationDemo />
      <PipelineDemo />
      <InstallSection />
      <HostedTeaser />
      <Footer />
    </main>
  );
}
