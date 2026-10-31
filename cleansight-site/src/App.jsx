import Nav from './components/Nav.jsx';
import Hero from './sections/Hero.jsx';
import Problem from './sections/Problem.jsx';
import HowItWorks from './sections/HowItWorks.jsx';
import Demo from './sections/Demo.jsx';
import Who from './sections/Who.jsx';
import Evidence from './sections/Evidence.jsx';
import Limits from './sections/Limits.jsx';
import Involved from './sections/Involved.jsx';
import Team from './sections/Team.jsx';
import Footer from './sections/Footer.jsx';

export default function App() {
  return (
    <>
      <a className="skip-link" href="#main">Skip to content</a>
      <Nav />
      <main id="main">
        <Hero />
        <Problem />
        <HowItWorks />
        <Demo />
        <Who />
        <Evidence />
        <Limits />
        <Involved />
        <Team />
      </main>
      <Footer />
    </>
  );
}
