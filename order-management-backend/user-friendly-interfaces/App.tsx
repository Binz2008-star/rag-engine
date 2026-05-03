import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Route, Switch } from "wouter";
import ErrorBoundary from "./components/ErrorBoundary";
import { ThemeProvider } from "./contexts/ThemeContext";
import Home from "./pages/Home";
import SellerDashboard from "./pages/SellerDashboard";
import SellerOrders from "./pages/SellerOrders";
import SellerProducts from "./pages/SellerProducts";
import CustomerStorefront from "./pages/CustomerStorefront";
import AdminPanel from "./pages/AdminPanel";
import OrderDetail from "./pages/OrderDetail";
import NotFound from "./pages/NotFound";

function Router() {
  return (
    <Switch>
      <Route path="/" component={Home} />
      <Route path="/seller/dashboard" component={SellerDashboard} />
      <Route path="/seller/orders" component={SellerOrders} />
      <Route path="/seller/products" component={SellerProducts} />
      <Route path="/store/:slug" component={CustomerStorefront} />
      <Route path="/admin" component={AdminPanel} />
      <Route path="/seller/orders/:orderId" component={OrderDetail} />
      <Route path="/404" component={NotFound} />
      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider defaultTheme="light">
        <TooltipProvider>
          <Toaster />
          <Router />
        </TooltipProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
